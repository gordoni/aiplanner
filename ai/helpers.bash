# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

AIPLANNER_HOME=${AIPLANNER_HOME:-$HOME/aiplanner}
AI_DIR=$AIPLANNER_HOME/ai
source $AI_DIR/setenv

EXTRA_ARGS="$@"

PARALLEL=${PARALLEL:-True}
    # "False": run seeds of a job sequentially rather than in parallel.
    # "True": run seeds of a job in parallel.
# "Jobs": run seeds and jobs in parallel; need to then wait; train.log is not saved.
RAY_CLUSTER=${RAY_CLUSTER:-$AI_DIR/cluster.yaml}
RAY_AUTOSCALER=${RAY_AUTOSCALER:-False} # Set to "True" to perform training with the Ray autoscaler enabled.
RAY_AUTOSCALER_USE_HEAD=${RAY_AUTOSCALER_USE_HEAD:-False} # Set to True to make use of the head node or False to minimize computation on the head node.
RAY_REDIS_ADDRESS=${RAY_REDIS_ADDRESS:-localhost:6379}
SEED_START=${SEED_START:-0}
SEEDS=${SEEDS:-10}
POLICY=${POLICY:-none}
ALGORITHM=${ALGORITHM:-PPO}
EVALUATOR=${EVALUATOR:-$AI_DIR/eval_model.py --redis-address=$RAY_REDIS_ADDRESS}
BASE_ARGS=${BASE_ARGS:--c $AI_DIR/aiplanner-scenario.txt}
TRAIN_ARGS=${TRAIN_ARGS:--c $AI_DIR/aiplanner-scenario-train.txt}

SINGLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-single-eval.txt"
COUPLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-couple-eval.txt"

start_ray_if_needed() {

    local HOST=`echo $RAY_REDIS_ADDRESS | sed 's/:.*//'`
    local PORT=`echo $RAY_REDIS_ADDRESS | sed 's/.*://'`

    nc -z $HOST $PORT && return

    if [ $HOST = localhost ]; then

        local ARGS
        if [ $RAY_AUTOSCALER = True ]; then
            ARGS="--autoscaling-config=$RAY_CLUSTER"
            if [ $RAY_AUTOSCALER_USE_HEAD = False ]; then
                ARGS="$ARGS --num-cpus=1 --num-gpus=0"
                    # --num-cpus=0 results in a ray.tune.run_experiments() error.
            fi
        else
            ARGS=
        fi

        (ulimit -n 65536; ray start --head --redis-port=$PORT $ARGS)

    fi
}

train () {

    local MODEL_NAME=$1
    local ARGS=$2

    case $ALGORITHM in
        A2C|A3C|PG|DDPG|APPO|PPO|PPO.baselines)
            start_ray_if_needed
            local TRAINER="$AI_DIR/train_rllib.py --redis-address=$RAY_REDIS_ADDRESS --train-algorithm=$ALGORITHM"
            local TRAINER_PARALLEL=True
            ;;
        ppo1)
            local TRAINER=$AI_DIR/train_ppo1.py
            local TRAINER_PARALLEL=False
            ;;
        td3|sac|trpo|ppo|ddpg|vpg)
            local TRAINER="$AI_DIR/train_spinup.py --train-algorithm=$ALGORITHM"
            local TRAINER_PARALLEL=False
            ;;
    esac

    local MODEL_DIR=aiplanner.$MODEL_NAME.tf

    if [ $TRAINER_PARALLEL = True ]; then

        local TEMPFILE=`tempfile -p train`
        if [ $PARALLEL = True -o $PARALLEL = Jobs ]; then
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED_START --train-seeds=$SEEDS $EXTRA_ARGS > $TEMPFILE 2>&1 &
            if [ $PARALLEL = True ]; then
                wait
                mv $TEMPFILE $MODEL_DIR/train.log
            fi
        else
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED_START --train-seeds=$SEEDS $EXTRA_ARGS 2>&1 | tee -a $TEMPFILE || exit 1
            mv $TEMPFILE $MODEL_DIR/train.log
        fi

    elif [ $PARALLEL = True -o $PARALLEL = Jobs ]; then

        local SEED=$SEED_START
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            # Output directory gets deleted hence we can't write the log within it; instead log to a tempfile.
            local TEMPFILE=`tempfile -p train`
            local TEMPFILES[$SEED]=$TEMPFILE
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED $EXTRA_ARGS > $TEMPFILE 2>&1 &
            SEED=`expr $SEED + 1`
        done

        if [ $PARALLEL = True ]; then
            wait
            local SEED=$SEED_START
            while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
                local MODEL_SEED_DIR=$MODEL_DIR/seed_$SEED
                if [ ! -d $MODEL_SEED_DIR ]; then
                    echo "Training failed: $MODEL_SEED_DIR" >&2
                    mkdir -p $MODEL_SEED_DIR
                fi
                mv ${TEMPFILES[$SEED]} $MODEL_SEED_DIR/train.log
                SEED=`expr $SEED + 1`
            done
        fi

    else

        local SEED=$SEED_START
        set -o pipefail
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local TEMPFILE=`tempfile -p train`
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED $EXTRA_ARGS 2>&1 | tee -a $TEMPFILE || exit 1
            mv $TEMPFILE $MODEL_DIR/train.log
            SEED=`expr $SEED + 1`
        done

    fi
}

evaluate () {

    local MODEL_NAME=$1
    local EVAL_NAME=$2
    local ARGS=$3

    local MODEL_DIR=aiplanner.$MODEL_NAME.tf
    local RESULT_DIR=$MODEL_DIR/$EVAL_NAME

    mkdir $RESULT_DIR 2> /dev/null

    if echo "$ARGS" | grep -q -- --ensemble; then
        local ENSEMBLE=True
        local ENSEMBLE_SUFFIX='-all'
    else
        local ENSEMBLE=False
        local ENSEMBLE_SUFFIX=
    fi

    if [ $ENSEMBLE = True -o "$MODEL_DIR/seed_*/tensorflow" = "$MODEL_DIR"'/seed_*/tensorflow' ]; then

        start_ray_if_needed

        $EVALUATOR $BASE_ARGS --model-dir=$MODEL_DIR --train-seed=$SEED_START --train-seeds=$SEEDS --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS \
            > $RESULT_DIR/evaluate$ENSEMBLE_SUFFIX.log 2>&1 &
        if [ $PARALLEL = True -o $PARALLEL = False ]; then
            wait
        fi

    elif [ $PARALLEL = True -o $PARALLEL = Jobs ]; then

        local SEED=$SEED_START
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            $EVALUATOR $BASE_ARGS --model-dir=$MODEL_DIR --train-seed=$SEED --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS > $RESULT_DIR/evaluate-seed_$SEED.log 2>&1 &
            SEED=`expr $SEED + 1`
        done

        if [ $PARALLEL = True ]; then
            wait
        fi

    else
    
        local SEED=$SEED_START
        set -o pipefail
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            $EVALUATOR $BASE_ARGS --model-dir=$MODEL_DIR --train-seed=$SEED --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS 2>&1 \
                | tee $RESULT_DIR/evaluate-seed_$SEED.log || exit 1
            SEED=`expr $SEED + 1`
        done

    fi
}

evaluate_with_policy () {

    local GAMMA=$1
    local EVAL_NAME=$2
    local ARGS=$3

    local MODEL_NAME="gamma$GAMMA"

    evaluate $MODEL_NAME $EVAL_NAME "$ARGS"

    if [ $POLICY = pmt-stocks ]; then
        local OLD_SEEDS=$SEEDS
        SEEDS=1
        for PMT_RETURN in -0.08 -0.06 -0.04 -0.02 0 0.02; do
            if expr $GAMMA '>=' 6 > /dev/null; then
                evaluate $MODEL_NAME $EVAL_NAME-pmt$PMT_RETURN-stocks0.5 "$ARGS --master-consume-policy=pmt --master-consume-policy-return=$PMT_RETURN "'--master-asset-allocation-policy={"stocks":0.5,"nominal_bonds":0.5}'
            fi
            if expr $GAMMA '>=' 3 > /dev/null; then
                evaluate $MODEL_NAME $EVAL_NAME-pmt$PMT_RETURN-stocks0.75 "$ARGS --master-consume-policy=pmt --master-consume-policy-return=$PMT_RETURN "'--master-asset-allocation-policy={"stocks":0.75,"nominal_bonds":0.25}'
            fi
            evaluate $MODEL_NAME $EVAL_NAME-pmt$PMT_RETURN-stocks1 "$ARGS --master-consume-policy=pmt --master-consume-policy-return=$PMT_RETURN "'--master-asset-allocation-policy={"stocks":1,"nominal_bonds":0}'
        done
        SEEDS=$OLD_SEEDS
    fi
}

args () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    ARGS="$ARGS --master-gamma=$GAMMA"
    if [ $UNIT = single ]; then
        echo "$ARGS"
    elif [ $UNIT = couple ]; then
        echo "$ARGS --master-sex2=male"
    else
        echo "$ARGS --master-sex2=female --master-couple-death-concordant --master-income-preretirement-concordant --master-consume-preretirement=6e4 --master-consume-additional=1"
    fi
}

eval_args () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    if [ $UNIT = single ]; then
        echo "$SINGLE_EVAL_ARGS"
    else
        echo "$COUPLE_EVAL_ARGS"
    fi
}

train_scenarios () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    ARGS=`args "$@"`
    local EVAL_ARGS=`eval_args "$@"`

    if [ $TRAINING = specific ]; then
        #train gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-p-tax-free=2e5"
        #train gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-p-tax-free=5e5"
        #train gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-p-tax-free=1e6"
        #train gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-p-tax-free=2e6"
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e5"
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=5e5"
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=1e6"
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-p-type ]; then
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
        train gamma$GAMMA-retired65-guaranteed_income20e3-tax_deferred2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e6"
        train gamma$GAMMA-retired65-guaranteed_income20e3-taxable-stocks2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = specific-spias ]; then
        train gamma$GAMMA-spias65-retired-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=65 --master-age-start=65 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias75-retired-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=65 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias85-retired-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=65 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias65-retired-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=65 --master-age-start=65 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias75-retired-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=65 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias85-retired-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=65 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-spias-le ]; then
        train gamma$GAMMA-spias-retired65-le_additional-1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=-1 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired65-le_additional1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=1 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired65-le_additional3-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=3 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired65-le_additional5-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = preretirement-gi -o $TRAINING = retired-gi ]; then
        local STAGE=`echo $TRAINING | sed 's/-.*//'`
        # If gi_fraction_low is set to zero, without any guaranteed income, during training at advanced ages the projected consumption
        # may be very small. As a result the reward_to_go observation will be many times larger than the observation range.
        # This may lead to poor training and/or training failing with a negative infinity reward_to_go estimate.
        #train $STAGE-gamma$GAMMA-gi_fraction0.03_0.1 "$ARGS --master-gi-fraction-low=0.03 --master-gi-fraction-high=0.1"
        train $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 "$ARGS --master-gi-fraction-low=0.1 --master-gi-fraction-high=0.3"
        #train $STAGE-gamma$GAMMA-gi_fraction0.3_1.0 "$ARGS --master-gi-fraction-low=0.3 --master-gi-fraction-high=1.0"
    elif [ $TRAINING = preretirement-le -o $TRAINING = retired-le ]; then
        local STAGE=`echo $TRAINING | sed 's/-.*//'`
        train $STAGE-gamma$GAMMA-le_additional-2.5_-0.5 "$ARGS --master-life-expectancy-additional-low=-2.5 --master-life-expectancy-additional-high=-0.5"
        train $STAGE-gamma$GAMMA-le_additional-0.5_1.5 "$ARGS --master-life-expectancy-additional-low=-0.5 --master-life-expectancy-additional-high=1.5"
        train $STAGE-gamma$GAMMA-le_additional1.5_3.5 "$ARGS --master-life-expectancy-additional-low=1.5 --master-life-expectancy-additional-high=3.5"
        train $STAGE-gamma$GAMMA-le_additional3.5_5.5 "$ARGS --master-life-expectancy-additional-low=3.5 --master-life-expectancy-additional-high=5.5"
    elif [ $TRAINING = generic ]; then
        train gamma$GAMMA "$ARGS"
    fi

}

eval_scenarios () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    ARGS=`args "$@"`
    local EVAL_ARGS=`eval_args "$@"`

    if [ $TRAINING = specific ]; then
        #evaluate gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free2e5 age_start50-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-p-tax-free=2e5"
        #evaluate gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free5e5 age_start50-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-p-tax-free=5e5"
        #evaluate gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free1e6 age_start50-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-p-tax-free=1e6"
        #evaluate gamma$GAMMA-age_start50-age_retirement65-guaranteed_income20e3-tax_free2e6 age_start50-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e5 retired65-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e5"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_free5e5 retired65-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=5e5"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_free1e6 retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e6 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-p-type ]; then
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_free2e6 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-tax_deferred2e6 retired65-guaranteed_income20e3-tax_deferred2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e6"
        evaluate gamma$GAMMA-retired65-guaranteed_income20e3-taxable2e6 retired65-guaranteed_income20e3-taxable2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = specific-spias ]; then
        evaluate gamma$GAMMA-spias65-retired65-guaranteed_income20e3-tax_free1e6 retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=65 --master-age-start=65 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias75-retired65-guaranteed_income20e3-tax_free1e6 retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=65 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias85-retired65-guaranteed_income20e3-tax_free1e6 retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=65 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias65-retired65-guaranteed_income20e3-tax_free2e6 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=65 --master-age-start=65 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias75-retired65-guaranteed_income20e3-tax_free2e6 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=65 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias85-retired65-guaranteed_income20e3-tax_free2e6 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=65 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-spias-le ]; then
        evaluate gamma$GAMMA-spias-retired65-le_additional-1-guaranteed_income20e3-tax_free2e6 retired65-le-5-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=-1 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired65-le_additional1-guaranteed_income20e3-tax_free2e6 retired65-le0-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=1 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired65-le_additional3-guaranteed_income20e3-tax_free2e6 retired65-le0-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=3 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired65-le_additional5-guaranteed_income20e3-tax_free2e6 retired65-le5-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = preretirement-gi ]; then
        evaluate preretirement-gamma$GAMMA-gi_fraction0.1_0.3 age50-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=50 --master-p-tax-free=1e6" # gi_fraction: 0.27
    elif [ $TRAINING = retired-gi ]; then
        evaluate retired-gamma$GAMMA-gi_fraction0.3_1.0 retired65-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e5" # gi_fraction: 0.71
        evaluate retired-gamma$GAMMA-gi_fraction0.3_1.0 retired65-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=5e5" # gi_fraction: 0.49
        evaluate retired-gamma$GAMMA-gi_fraction0.3_1.0 retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=1e6" # gi_fraction: 0.32
        evaluate retired-gamma$GAMMA-gi_fraction0.1_0.3 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6" # gi_fraction: 0.20
        evaluate retired-gamma$GAMMA-gi_fraction0.03_0.1 retired65-guaranteed_income20e3-tax_free5e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=5e6" # gi_fraction: 0.09
    elif [ $TRAINING = retired-gi-p-type ]; then
        evaluate retired-gamma$GAMMA-gi_fraction0.1_0.3 retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
        evaluate retired-gamma$GAMMA-gi_fraction0.1_0.3 retired65-guaranteed_income20e3-tax_deferred2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e6"
        evaluate retired-gamma$GAMMA-gi_fraction0.1_0.3 retired65-guaranteed_income20e3-taxable2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = preretirement-le ]; then
        evaluate preretirement-gamma$GAMMA-le_additional1.5_3.5 age50-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=50 --master-p-tax-free=1e6"
    elif [ $TRAINING = retired-le ]; then
        evaluate retired-gamma$GAMMA-le_additional-2.5_-0.5 retired65-le_additional-1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=-1  --master-p-tax-free=2e6"
        evaluate retired-gamma$GAMMA-le_additional-0.5_1.5 retired65-le_additional1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=1  --master-p-tax-free=2e6"
        evaluate retired-gamma$GAMMA-le_additional1.5_3.5 retired65-le_additional3-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=3 --master-p-tax-free=2e6"
        evaluate retired-gamma$GAMMA-le_additional3.5_5.5 retired65-le_additional5-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-life-expectancy-additional=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = generic ]; then
        #evaluate_with_policy $GAMMA age_start50-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-p-tax-free=2e5"
        #evaluate_with_policy $GAMMA age_start50-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-p-tax-free=5e5"
        #evaluate_with_policy $GAMMA age_start50-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-p-tax-free=1e6"
        #evaluate_with_policy $GAMMA age_start50-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-p-tax-free=2e6"
        evaluate_with_policy $GAMMA retired65-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e5"
        evaluate_with_policy $GAMMA retired65-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=5e5"
        evaluate_with_policy $GAMMA retired65-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=1e6"
        evaluate_with_policy $GAMMA retired65-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-free=2e6"
    fi
}

train_eval () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    echo `date` Training $EPISODE
    train_scenarios "$@"

    wait

    echo `date` Evaluating $EPISODE
    eval_scenarios "$@"

    wait
}

timesteps () {

    local UNIT=$1
    local SPIAS=$2

    if [ $UNIT = single ]; then
        if [ $SPIAS = no_spias ]; then
            echo 2000000
        else
            echo 5000000
        fi
    elif [ $UNIT = couple ]; then
        echo 10000000
    fi
}

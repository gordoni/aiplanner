# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
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
RAY_AUTOSCALER=${RAY_AUTOSCALER:-True} # Set to "False" to perform training without the Ray autoscaler enabled.
RAY_AUTOSCALER_USE_HEAD=${RAY_AUTOSCALER_USE_HEAD:-False}
    # "False": Head node will not be used as a worker.
    # "True": Head node will be used for possibly multiple cpu workers.
RAY_ADDRESS=${RAY_ADDRESS:-localhost:6379}
SEED_START=${SEED_START:-0}
SEEDS=${SEEDS:-10}
POLICY=${POLICY:-none}
ALGORITHM=${ALGORITHM:-PPO}
EVALUATOR=${EVALUATOR:-$AI_DIR/eval_model.py --address=$RAY_ADDRESS}
BASE_SCENARIO=${BASE_SCENARIO:-$AI_DIR/aiplanner-scenario.txt}
BASE_ARGS=${BASE_ARGS:--c $BASE_SCENARIO}
TRAIN_ARGS=${TRAIN_ARGS:--c $AI_DIR/aiplanner-scenario-train.txt}

SINGLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-single-eval.txt"
COUPLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-couple-eval.txt"

start_ray_if_needed() {

    local HOST=`echo $RAY_ADDRESS | sed 's/:.*//'`
    local PORT=`echo $RAY_ADDRESS | sed 's/.*://'`

    nc -z $HOST $PORT && return

    if [ $HOST = localhost ]; then

        local ARGS
        if [ $RAY_AUTOSCALER = True ]; then
            ARGS="--autoscaling-config=$RAY_CLUSTER"
            if [ $RAY_AUTOSCALER_USE_HEAD != True ]; then
                ARGS="$ARGS --num-cpus=0 --num-gpus=0"
            fi
        else
            ARGS=
        fi

        (
            ulimit -n 65536
            nohup ray start --head --port=$PORT $ARGS
        ) > /tmp/ray.out 2>&1

    fi
}

train () {

    local MODEL_NAME=$1
    local ARGS=$2

    case $ALGORITHM in
        A2C|A3C|PG|DDPG|APPO|PPO|PPO.baselines)
            start_ray_if_needed
            local TRAINER="$AI_DIR/train_rllib.py --address=$RAY_ADDRESS --train-algorithm=$ALGORITHM"
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
    TRAINER="nohup $TRAINER"

    local MODEL_DIR=aiplanner-$MODEL_NAME.tf

    if [ $TRAINER_PARALLEL = True ]; then

        local TEMPFILE=`tempfile -p train`
        if [ $PARALLEL = True -o $PARALLEL = Jobs ]; then
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seeds=$SEEDS $EXTRA_ARGS > $TEMPFILE 2>&1 &
            if [ $PARALLEL = True ]; then
                wait
                mv $TEMPFILE $MODEL_DIR/train.log
            fi
        else
            $TRAINER $BASE_ARGS $TRAIN_ARGS --model-dir=$MODEL_DIR $ARGS --train-seeds=$SEEDS $EXTRA_ARGS 2>&1 | tee -a $TEMPFILE || exit 1
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

    local MODEL_DIR=aiplanner-$MODEL_NAME.tf
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

evaluate_policy () {

    local GAMMA=$1
    local EVAL_NAME=$2
    local ARGS=$3

    local MODEL_NAME="gamma$GAMMA"

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
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6

    ARGS="$ARGS --master-gamma=$GAMMA"

    if [ "$UNIT" = single ]; then
        ARGS="$ARGS"
    elif [ "$UNIT" = couple ]; then
        ARGS="$ARGS --master-sex2=male"
    elif [ "$UNIT" = concordant ]; then
        ASRGS="$ARGS --master-sex2=female --master-couple-death-concordant --master-couple-spias --master-income-preretirement-concordant --master-consume-preretirement=6e4 --master-consume-additional=1"
    else
        echo "Unknown unit: $UNIT" >&2
        exit 1
    fi

    if [ "$SPIAS" = none ]; then
        ARGS="$ARGS"
    elif [ "$SPIAS" = real ]; then
        ARGS="$ARGS --master-real-spias"
    elif [ "$SPIAS" = nominal ]; then
        ARGS="$ARGS --master-nominal-spias"
    else
        echo "Unknown unit: $UNIT" >&2
        exit 1
    fi

    echo "$ARGS"
}

train_args () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6

    TARGS="--train-max-failures=100" # Recommended for long training runs.
    case "$TRAINING" in
        specific*)
            ;;
        *)
            case "$STAGE" in
                preretirement)
                    ;;
                retired)
                    TARGS="$TARGS --master-age-start=50 --master-age-retirement=0 --master-p-weighted-low=1e4 --master-p-weighted-high=1e7"
                    ;;
                *)
                    echo "Unknown stage: $STAGE" >&2
                    exit 1
                    ;;
            esac
            ;;
    esac

    echo "$TARGS"
}

eval_args () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6

    if [ $UNIT = single ]; then
        echo "$SINGLE_EVAL_ARGS"
    else
        echo "$COUPLE_EVAL_ARGS"
    fi
}

COMPLEX_SCENARIO='--master-age-start=30 --master-income-preretirement=120e3 --master-consume-preretirement=50e3 --master-guaranteed-income=[{"start":null,"payout":20e3,"source_of_funds":"taxable","type":"social_security"},{"start":30,"end":50,"payout":-5e3,"inflation_adjustment":0,"source_of_funds":"tax_free"},{"start":30,"end":43,"payout":-10e3,"source_of_funds":"tax_free"},{"start":43,"end":47,"payout":-30e3,"source_of_funds":"tax_free"},{"start":35,"end":36,"payout":-50e3,"source_of_funds":"tax_free"},{"start":35,"end":65,"payout":-20e3,"inflation_adjustment":0,"source_of_funds":"tax_free"}]'
    # 20k Social Security - taxable, unlike mistakenly non-taxable elsewhere.
    # 5k nominal student loan - 20 years remaining.
    # 10k child - child currently age 5 suppport until 18.
    # 30k college - at child's age 18 for 4 years.
    # 50k home down payment - at age 35.
    # 20k nominal mortgage - at age 35 for 30 years (starting amount not adjusted for inflation).

train_scenarios () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6

    ARGS=`args "$@"`
    local EVAL_ARGS=`eval_args "$@"`
    local TARGS=`train_args "$@"`
    ARGS="$TARGS $ARGS"

    if [ "$SPIAS" = none ]; then
        SPIAS=no_spias
    else
        SPIAS=spias
    fi

    if [ $TRAINING = specific ]; then
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e5 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e5"
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_free5e5 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=5e5"
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=1e6"
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-p-type ]; then
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e6"
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_deferred2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-deferred=2e6"
        train gamma$GAMMA-retired67-guaranteed_income20e3-taxable-stocks2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = specific-spias ]; then
        train gamma$GAMMA-spias67-retired67-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=67 --master-age-start=67 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias75-retired67-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=67 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias85-retired67-guaranteed_income20e3-tax_free1e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=67 --master-p-tax-free=1e6"
        train gamma$GAMMA-spias67-retired67-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=67 --master-age-start=67 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias75-retired67-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=67 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias85-retired67-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=67 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-spias-le ]; then
        train gamma$GAMMA-spias-retired67-le_additional-1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=-1 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired67-le_additional1-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=1 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired67-le_additional3-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=3 --master-p-tax-free=2e6"
        train gamma$GAMMA-spias-retired67-le_additional5-guaranteed_income20e3-tax_free2e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-tax_diverse ]; then
        train gamma$GAMMA-age50-tax_diverse2e5 "$EVAL_ARGS $ARGS --master-age-start=50 --master-p-tax-free=0.5e5 --master-p-tax-deferred=1.0e5 --master-p-taxable-stocks=0.3e5 --master-p-taxable-real-bonds=0.2e5"
        train gamma$GAMMA-retired67-guaranteed_income20e3-tax_diverse1e6 "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2.5e5 --master-p-tax-deferred=5.0e5 --master-p-taxable-stocks=1.5e5 --master-p-taxable-real-bonds=1e5"
    elif [ $TRAINING = specific-p_none ]; then
        train $SPIAS-gamma$GAMMA "$EVAL_ARGS $ARGS --master-age-start=30 --master-income-preretirement=80e3 --master-consume-preretirement=50e3"
    elif [ $TRAINING = specific-p_none_complex ]; then
        train $SPIAS-gamma$GAMMA-complex "$EVAL_ARGS $ARGS $COMPLEX_SCENARIO"
    elif [ $TRAINING = slice-gi ]; then
        # No spias case - slice and dice based on guaranteed income fraction.
        # If gi_fraction_low is set to zero, without any guaranteed income, during training at advanced ages the projected consumption
        # may be very small. As a result the reward_to_go observation will be many times larger than the observation range.
        # This may lead to poor training and/or training failing with a negative infinity reward_to_go estimate.
        train $STAGE-gamma$GAMMA-gi_fraction0.03_0.1 "$ARGS --master-gi-fraction-low=0.03 --master-gi-fraction-high=0.1"
        train $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 "$ARGS --master-gi-fraction-low=0.1 --master-gi-fraction-high=0.3"
        train $STAGE-gamma$GAMMA-gi_fraction0.3_1.0 "$ARGS --master-gi-fraction-low=0.3 --master-gi-fraction-high=1.0"
    elif [ $TRAINING = slice-le ]; then
        # Spias case - slice and dice based on le_additional.
        # Probably also need to train separately for male and female as spias_permitted_to_age appears at different remaining years_retire values.
        # Not clear how to handle couples because age difference is variable.
        train $STAGE-gamma$GAMMA-le_additional-2.5_-0.5 "$ARGS --master-life-expectancy-additional-low=-2.5 --master-life-expectancy-additional-high=-0.5 --master-life-expectancy-additional2-low=-2.5 --master-life-expectancy-additional2-high=-0.5"
        train $STAGE-gamma$GAMMA-le_additional-0.5_1.5 "$ARGS --master-life-expectancy-additional-low=-0.5 --master-life-expectancy-additional-high=1.5 --master-life-expectancy-additional2-low=-0.5 --master-life-expectancy-additional2-high=1.5"
        train $STAGE-gamma$GAMMA-le_additional1.5_3.5 "$ARGS --master-life-expectancy-additional-low=1.5 --master-life-expectancy-additional-high=3.5 --master-life-expectancy-additional2-low=1.5 --master-life-expectancy-additional2-high=3.5"
        train $STAGE-gamma$GAMMA-le_additional3.5_5.5 "$ARGS --master-life-expectancy-additional-low=3.5 --master-life-expectancy-additional-high=5.5 --master-life-expectancy-additional2-low=3.5 --master-life-expectancy-additional2-high=5.5"
    elif [ $TRAINING = generic ]; then
        train $STAGE-$SPIAS-gamma$GAMMA "$ARGS"
    fi

}

eval_scenarios () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6
    local EVALUATE=${7:-tax_free}
    local LABEL=$8

    ARGS=`args "$@"`
    local EVAL_ARGS=`eval_args "$@"`

    if [ "$SPIAS" = none ]; then
        SPIAS=no_spias
    else
        SPIAS=spias
    fi

    if [ -n "$LABEL" ]; then
        LABEL="-$LABEL"
    fi

    if [ $TRAINING = specific ]; then
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e5 $UNIT-retired67-guaranteed_income20e3-tax_free2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e5"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_free5e5 $UNIT-retired67-guaranteed_income20e3-tax_free5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=5e5"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_free1e6 $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-p-type ]; then
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_deferred2e6 $UNIT-retired67-guaranteed_income20e3-tax_deferred2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-deferred=2e6"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-taxable2e6 $UNIT-retired67-guaranteed_income20e3-taxable2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = specific-spias ]; then
        evaluate gamma$GAMMA-spias67-retired67-guaranteed_income20e3-tax_free1e6 $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=67 --master-age-start=67 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias75-retired67-guaranteed_income20e3-tax_free1e6 $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=67 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias85-retired67-guaranteed_income20e3-tax_free1e6 $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=67 --master-p-tax-free=1e6"
        evaluate gamma$GAMMA-spias67-retired67-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=67 --master-age-start=67 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias75-retired67-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=75 --master-age-start=67 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias85-retired67-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-spias-permitted-from-age=100 --master-spias-at-age=85 --master-age-start=67 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-spias-le ]; then
        evaluate gamma$GAMMA-spias-retired67-le_additional-1-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-le-5-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=-1 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired67-le_additional1-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-le0-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=1 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired67-le_additional3-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-le0-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=3 --master-p-tax-free=2e6"
        evaluate gamma$GAMMA-spias-retired67-le_additional5-guaranteed_income20e3-tax_free2e6 $UNIT-retired67-le5-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-life-expectancy-additional=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = specific-tax_diverse ]; then
        evaluate gamma$GAMMA-age50-tax_diverse2e5 $UNIT-age50-tax_diverse2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-p-tax-free=0.5e5 --master-p-tax-deferred=1.0e5 --master-p-taxable-stocks=0.3e5 --master-p-taxable-real-bonds=0.2e5"
        evaluate gamma$GAMMA-retired67-guaranteed_income20e3-tax_diverse1e6 $UNIT-retired67-guaranteed_income20e3-tax_diverse1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-p-tax-free=2.5e5 --master-p-tax-deferred=5.0e5 --master-p-taxable-stocks=1.5e5 --master-p-taxable-real-bonds=1.0e5"
    elif [ $TRAINING = specific-p_none ]; then
        evaluate $SPIAS-gamma$GAMMA $UNIT$LABEL "$EVAL_ARGS $ARGS --master-age-start=30 --master-income-preretirement=80e3 --master-consume-preretirement=50e3"
    elif [ $TRAINING = specific-p_none_complex ]; then
        evaluate $SPIAS-gamma$GAMMA-complex $UNIT$LABEL "$EVAL_ARGS $ARGS $COMPLEX_SCENARIO"
    elif [ $TRAINING = slice-gi -a $STAGE = preretirement ]; then
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 $UNIT-age50-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=1e6" # gi_fraction: 0.27
    elif [ $TRAINING = slice-gi -a $STAGE = retired ]; then
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.3_1.0 $UNIT-retired67-guaranteed_income20e3-tax_free2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=2e5" # gi_fraction: 0.71
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.3_1.0 $UNIT-retired67-guaranteed_income20e3-tax_free5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=5e5" # gi_fraction: 0.49
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.3_1.0 $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=1e6" # gi_fraction: 0.32
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=2e6" # gi_fraction: 0.20
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.03_0.1 $UNIT-retired67-guaranteed_income20e3-tax_free5e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=5e6" # gi_fraction: 0.09
    elif [ $TRAINING = slice-gi-p-type -a $STAGE = retired ]; then
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=2e6"
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 $UNIT-retired67-guaranteed_income20e3-tax_deferred2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-deferred=2e6"
        evaluate $STAGE-gamma$GAMMA-gi_fraction0.1_0.3 $UNIT-retired67-guaranteed_income20e3-taxable2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-taxable-stocks=2e6"
    elif [ $TRAINING = slice-le -a $STAGE = preretirement ]; then
        evaluate $STAGE-gamma$GAMMA-le_additional1.5_3.5 $UNIT-age50-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=1e6"
    elif [ $TRAINING = slice-le -a $STAGE = retired ]; then
        evaluate $STAGE-gamma$GAMMA-le_additional-2.5_-0.5 $UNIT-retired67-le_additional-1-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-life-expectancy-additional=-1 --master-life-expectancy-additional2=-1 --master-p-tax-free=2e6"
        evaluate $STAGE-gamma$GAMMA-le_additional-0.5_1.5 $UNIT-retired67-le_additional1-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-life-expectancy-additional=1 --master-life-expectancy-additional2=1 --master-p-tax-free=2e6"
        evaluate $STAGE-gamma$GAMMA-le_additional1.5_3.5 $UNIT-retired67-le_additional3-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-life-expectancy-additional=3 --master-life-expectancy-additional2=3 --master-p-tax-free=2e6"
        evaluate $STAGE-gamma$GAMMA-le_additional3.5_5.5 $UNIT-retired67-le_additional5-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-life-expectancy-additional=5 --master-life-expectancy-additional2=5 --master-p-tax-free=2e6"
    elif [ $TRAINING = generic -a $STAGE = preretirement ]; then
        case "$EVALUATE" in
            tax_free)
                evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_free2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=2e5"
                evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_free5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=5e5"
                evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=1e6"
                evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-tax-free=2e6"
                ;;
           tax_diverse)
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_diverse2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-weighted=2e5"
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_diverse5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-weighted=5e5"
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_diverse1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-weighted=1e6"
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age50-tax_diverse2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=50 --master-age-start2=50 --master-p-weighted=2e6"
               ;;
           p_none)
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age30-p_none$LABEL "$EVAL_ARGS $ARGS --master-age-start=30 --master-income-preretirement=80e3 --master-consume-preretirement=50e3"
               ;;
           p_none_complex)
               evaluate $STAGE-$SPIAS-gamma$GAMMA $UNIT-age30-p_none_complex$LABEL "$EVAL_ARGS $ARGS $COMPLEX_SCENARIO"
               ;;
        esac
    fi
    local MODEL_STAGE=${FORCE_STAGE:-$STAGE}
    if [ $TRAINING = generic -a $STAGE = retired ]; then
        case "$EVALUATE" in
            tax_free)
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_free2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=2e5"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_free5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=5e5"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_free1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=1e6"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_free2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=2e6"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_free5e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-tax-free=5e6"
                ;;
            tax_diverse)
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse2e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=2e5"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse5e5$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=5e5"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse1e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=1e6"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=2e6"
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse5e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=5e6"
                ;;
            tax_diverse2e6)
                evaluate $MODEL_STAGE-$SPIAS-gamma$GAMMA $UNIT-retired67-guaranteed_income20e3-tax_diverse2e6$LABEL "$EVAL_ARGS $ARGS --master-age-start=67 --master-age-start2=67 --master-p-weighted=2e6"
                ;;
        esac
    fi
}

train_eval () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5
    local ARGS=$6

    echo "`date` Training $UNIT $STAGE $SPIAS $GAMMA"
    train_scenarios "$@"

    wait

    echo "`date` Evaluating $UNIT $STAGE $SPIAS $GAMMA"
    eval_scenarios "$@"

    wait
}

timesteps () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5

    case "$TRAINING" in
        specific*)
            echo "--train-optimizer-step-size=5e-5 --train-num-timesteps=10000000 --train-batch-size=100000"
            return
            ;;
        *)
            # train: PPO, batch_size=500k, minibatch_size=500, optimizer_epochs=10, optimizer_step_size=2e-5, entropy_coefficient=1e-4, fcnet_hiddens 256x256
            # eval: gamma=6, age_start=50, age_retirement=50, p_weighted=2e6
            # old train: PPO, batch_size=200k, minibatch_size=128, optimizer_epochs=30, optimizer_step_size=5e-6, entropy_coefficient=0, fcnet_hiddens 256x256
            # old eval: gamma=6, p_weighted=2e6
            if [ $STAGE = preretirement ]; then
                if [ $SPIAS = none ]; then
                    echo "--train-num-timesteps=200000000"
                    # good (99.9%) 120m, asymptote 130m
                    # old: good 60m, asymptote 70m
                    return
                elif [ $SPIAS = real -o $SPIAS = nominal ]; then
                    echo "--train-num-timesteps=200000000"
                    # good (99.9%) 130m, aymptote 140m
                    # old: good 30m, asymptote 40m
                    return
                fi
            elif [ $STAGE = retired ]; then
                if [ $SPIAS = none ]; then
                    echo "--train-num-timesteps=150000000"
                    # good (99.9%) 100m, aymptote 110m
                    # old: good 30m, asymptote 40m
                    return
                elif [ $SPIAS = real -o $SPIAS = nominal ]; then
                    echo "--train-num-timesteps=200000000"
                    # good (99.9%) 160m, asymptote 170m
                    # old: good 60m, asymptote 80m
                    return
                fi
            fi
            ;;
    esac

    echo "Unknown stage: $STAGE" >&2
    exit 1
}

skip_model () {

    local TRAINING=$1
    local UNIT=$2
    local STAGE=$3
    local SPIAS=$4
    local GAMMA=$5

    if [ $STAGE = retired -a \( $SPIAS != none -o `echo $GAMMA | awk '{print int($1)}'` -lt 6 \) ]; then
        return 0
    else
        return 1
    fi
}

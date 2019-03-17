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
SEED_START=${SEED_START:-0}
SEEDS=${SEEDS:-10}
POLICY=${POLICY:-none}
ALGORITHM=${ALGORITHM:-ppo1}
EVALUATOR=${EVALUATOR:-$AI_DIR/eval_model.py}
BASE_ARGS=${BASE_ARGS:--c $AI_DIR/aiplanner-scenario.txt}
TRAIN_ARGS=${TRAIN_ARGS:--c $AI_DIR/aiplanner-scenario-train.txt}

SINGLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-single-eval.txt"
COUPLE_EVAL_ARGS="-c $AI_DIR/aiplanner-scenario-couple-eval.txt"

train () {

    local MODEL_NAME=$1
    local ARGS=$2

    case $ALGORITHM in
        A2C)
            ;&
        A3C)
            ;&
        PG)
            ;&
        DDPG)
            ;&
        APPO)
            ;&
        PPO)
            ;&
        PPO.baselines)
            local TRAINER="$AI_DIR/train_rllib.py --train-algorithm=$ALGORITHM"
            ;;
        ppo1)
            local TRAINER=$AI_DIR/train_ppo1.py
            ;;
        td3)
            ;&
        sac)
            ;&
        trpo)
            ;&
        ppo)
            ;&
        ddpg)
            ;&
        vpg)
            local TRAINER="$AI_DIR/train_spinup.py --train-algorithm=$ALGORITHM"
            ;;
    esac

    if [ $PARALLEL = True -o $PARALLEL = Jobs ]; then

        local SEED=$SEED_START
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local MODEL_DIR=aiplanner.$MODEL_NAME.tf
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
                local MODEL_SEED_DIR=aiplanner.$MODEL_NAME.tf/seed_$SEED
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
            local MODEL_DIR=aiplanner.$MODEL_NAME.tf
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

    if [ $PARALLEL = True -o $PARALLEL = Jobs ]; then

        local SEED=$SEED_START
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local MODEL_DIR=aiplanner.$MODEL_NAME-seed_$SEED.tf
            local RESULT_DIR=$MODEL_DIR/$EVAL_NAME
            mkdir $RESULT_DIR 2> /dev/null
            $EVALUATOR $BASE_ARGS --model-dir=$MODEL_DIR --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS > $RESULT_DIR/eval.log 2>&1 &
            SEED=`expr $SEED + 1`
        done

        if [ $PARALLEL = True ]; then
            wait
        fi

    else
    
        local SEED=$SEED_START
        set -o pipefail
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local MODEL_DIR=aiplanner.$MODEL_NAME-seed_$SEED.tf
            local RESULT_DIR=$MODEL_DIR/$EVAL_NAME
            mkdir $RESULT_DIR 2> /dev/null
            $EVALUATOR $BASE_ARGS --model-dir=$MODEL_DIR --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS 2>&1 | tee $RESULT_DIR/eval.log || exit 1
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

train_eval () {

    local TRAINING=$1
    local UNIT=$2
    local GAMMA=$3
    local EPISODE=$4
    local ARGS=$5

    ARGS="$ARGS --master-gamma=$GAMMA"
    if [ $UNIT = single ]; then
        local EVAL_ARGS=$SINGLE_EVAL_ARGS
    elif [ $UNIT = couple ]; then
        local EVAL_ARGS=$COUPLE_EVAL_ARGS
        ARGS="$ARGS --master-sex2=male"
    else
        local EVAL_ARGS=$COUPLE_EVAL_ARGS
        ARGS="$ARGS --master-sex2=female --master-couple-death-concordant --master-income-preretirement-concordant --master-consume-preretirement=6e4 --master-consume-additional=1"
    fi

    echo `date` Training $EPISODE

    if [ $TRAINING = both -o $TRAINING = specific ]; then
        train gamma$GAMMA-age_start50-age_retirement65-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-p-tax-deferred=5e5"
        train gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e5"
        train gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=5e5"
        train gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=1e6"
    fi
    if [ $TRAINING = both -o $TRAINING = generic ]; then
        train gamma$GAMMA "$ARGS"
    fi

    wait

    echo `date` Evaluating $EPISODE

    if [ $TRAINING = both -o $TRAINING = specific ]; then
        evaluate gamma$GAMMA-age_start50-age_retirement65-defined_benefits16e3-tax_deferrred5e5 age_start50-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-p-tax-deferred=5e5"
        evaluate gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred2e5 retired65-defined_benefits16e3-tax_deferrred2e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e5"
        evaluate gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred5e5 retired65-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=5e5"
        evaluate gamma$GAMMA-retired65-defined_benefits16e3-tax_deferrred1e6 retired65-defined_benefits16e3-tax_deferrred1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=1e6"
    fi

    if [ $TRAINING = both -o $TRAINING = generic ]; then
        evaluate_with_policy $GAMMA age_start50-defined_benefits16e3-tax_deferrred2.5e5 "$EVAL_ARGS $ARGS --master-p-tax-deferred=2.5e5"
        evaluate_with_policy $GAMMA age_start50-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-p-tax-deferred=5e5"
        evaluate_with_policy $GAMMA age_start50-defined_benefits16e3-tax_deferrred1e6 "$EVAL_ARGS $ARGS --master-p-tax-deferred=1e6"
        evaluate_with_policy $GAMMA age_start50-defined_benefits16e3-tax_deferrred2e6 "$EVAL_ARGS $ARGS --master-p-tax-deferred=2e6"
        evaluate_with_policy $GAMMA retired65-defined_benefits16e3-tax_deferrred2.5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2.5e5"
        evaluate_with_policy $GAMMA retired65-defined_benefits16e3-tax_deferrred5e5 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=5e5"
        evaluate_with_policy $GAMMA retired65-defined_benefits16e3-tax_deferrred1e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=1e6"
        evaluate_with_policy $GAMMA retired65-defined_benefits16e3-tax_deferrred2e6 "$EVAL_ARGS $ARGS --master-age-start=65 --master-p-tax-deferred=2e6"
    fi

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

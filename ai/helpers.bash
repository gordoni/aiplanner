# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
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
TRAINER=${TRAINER:-$AI_DIR/train_ppo1.py}
EVALUATOR=${EVALUATOR:-$AI_DIR/eval_model.py}
CONFIG_FILE=${CONFIG_FILE:-$AI_DIR/aiplanner-scenario.txt}
TRAIN_FILE=${TRAIN_FILE:-$AI_DIR/aiplanner-scenario-train.txt}

SINGLE_EVAL_FILE=$AI_DIR/aiplanner-scenario-single-eval.txt
COUPLE_EVAL_FILE=$AI_DIR/aiplanner-scenario-couple-eval.txt

train () {

    local MODEL_NAME=$1
    local ARGS=$2

    if [ $PARALLEL = True -o $PARALLEL = Jobs ]; then

        local SEED=$SEED_START
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local MODEL_DIR=aiplanner.$MODEL_NAME-seed_$SEED.tf
            # Output directory must not exist when tensorflow save() is called to save the model hence we can't write the log within it; instead log to a tempfile.
            local TEMPFILE=`tempfile -p train`
            local TEMPFILES[$SEED]=$TEMPFILE
            $TRAINER -c $CONFIG_FILE -c $TRAIN_FILE --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED $EXTRA_ARGS > $TEMPFILE 2>&1 &
            SEED=`expr $SEED + 1`
        done

        if [ $PARALLEL = True ]; then
            wait
            local SEED=$SEED_START
            while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
                local MODEL_DIR=aiplanner.$MODEL_NAME-seed_$SEED.tf
                if [ ! -d $MODEL_DIR ]; then
                    echo "Training failed: $MODEL_DIR" >&2
                fi
                mkdir -p $MODEL_DIR
                mv ${TEMPFILES[$SEED]} $MODEL_DIR/train.log
                SEED=`expr $SEED + 1`
            done
        fi

    else

        local SEED=$SEED_START
        set -o pipefail
        while [ $SEED -lt `expr $SEED_START + $SEEDS` ]; do
            local MODEL_DIR=aiplanner.$MODEL_NAME-seed_$SEED.tf
            local TEMPFILE=`tempfile -p train`
            $TRAINER -c $CONFIG_FILE -c $TRAIN_FILE --model-dir=$MODEL_DIR $ARGS --train-seed=$SEED $EXTRA_ARGS 2>&1 | tee -a $TEMPFILE || exit 1
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
            $EVALUATOR -c $CONFIG_FILE --model-dir=$MODEL_DIR --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS > $RESULT_DIR/eval.log 2>&1 &
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
            $EVALUATOR -c $CONFIG_FILE --model-dir=$MODEL_DIR --result-dir=$RESULT_DIR $ARGS $EXTRA_ARGS 2>&1 | tee $RESULT_DIR/eval.log || exit 1
            SEED=`expr $SEED + 1`
        done

    fi
}

train_eval_single () {

    local EPISODE="$1"

    echo `date` Training $EPISODE

    train age_start50-age_retirement65-defined_benefits16e3-tax_free5e5 "-c $SINGLE_EVAL_FILE --master-p-tax-free=5e5"
    train age_start50-age_retirement65-defined_benefits16e3-tax_deferred5e5 "-c $SINGLE_EVAL_FILE --master-p-tax-deferred=5e5"
    train age_start50-age_retirement65-defined_benefits16e3-taxable_stocks5e5 "-c $SINGLE_EVAL_FILE --master-p-taxable-stocks=5e5"
    train retired65-defined_benefits16e3-tax_free5e5 "-c $SINGLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=5e5"
    train gamma3 '--master-gamma=3'

    wait

    echo `date` Evaluating $EPISODE

    evaluate age_start50-age_retirement65-defined_benefits16e3-tax_free5e5 specific "-c $SINGLE_EVAL_FILE --master-p-tax-free=5e5"
    evaluate age_start50-age_retirement65-defined_benefits16e3-tax_deferred5e5 specific "-c $SINGLE_EVAL_FILE --master-p-tax-deferred=5e5"
    evaluate age_start50-age_retirement65-defined_benefits16e3-taxable_stocks5e5 specific "-c $SINGLE_EVAL_FILE --master-p-taxable-stocks=5e5"
    evaluate retired65-defined_benefits16e3-tax_free5e5 specific "-c $SINGLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=5e5"

    evaluate gamma3 age_start50-defined_benefits16e3-tax_free5e5 "-c $SINGLE_EVAL_FILE --master-p-tax-free=5e5"
    evaluate gamma3 age_start50-defined_benefits16e3-tax_deferred5e5 "-c $SINGLE_EVAL_FILE --master-p-tax-deferred=5e5"
    evaluate gamma3 age_start50-defined_benefits16e3-taxable_stocks5e5 "-c $SINGLE_EVAL_FILE --master-p-taxable-stocks=5e5"
    evaluate gamma3 retired65-defined_benefits16e3-tax_free5e5 "-c $SINGLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=5e5"

    wait
}

train_eval_couple () {

    local EPISODE="$1"

    echo `date` Training $EPISODE

    train age_start50-age_retirement65-defined_benefits32e3-tax_free1e6 "-c $COUPLE_EVAL_FILE --master-p-tax-free=1e6"
    train age_start50-age_retirement65-defined_benefits32e3-tax_deferred1e6 "-c $COUPLE_EVAL_FILE --master-p-tax-deferred=1e6"
    train age_start50-age_retirement65-defined_benefits32e3-taxable_stocks1e6 "-c $COUPLE_EVAL_FILE --master-p-taxable-stocks=1e6"
    train retired65-defined_benefits32e3-tax_free1e6 "-c $COUPLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=1e6"
    train gamma3 '--master-gamma=3'

    wait

    echo `date` Evaluating $EPISODE

    evaluate age_start50-age_retirement65-defined_benefits32e3-tax_free1e6 specific "-c $COUPLE_EVAL_FILE --master-p-tax-free=1e6"
    evaluate age_start50-age_retirement65-defined_benefits32e3-tax_deferred1e6 specific "-c $COUPLE_EVAL_FILE --master-p-tax-deferred=1e6"
    evaluate age_start50-age_retirement65-defined_benefits32e3-taxable_stocks1e6 specific "-c $COUPLE_EVAL_FILE --master-p-taxable-stocks=1e6"
    evaluate retired65-defined_benefits32e3-tax_free1e6 specific "-c $COUPLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=1e6"

    evaluate gamma3 age_start50-defined_benefits32e3-tax_free1e6 "-c $COUPLE_EVAL_FILE --master-p-tax-free=1e6"
    evaluate gamma3 age_start50-defined_benefits32e3-tax_deferred1e6 "-c $COUPLE_EVAL_FILE --master-p-tax-deferred=1e6"
    evaluate gamma3 age_start50-defined_benefits32e3-taxable_stocks1e6 "-c $COUPLE_EVAL_FILE --master-p-taxable-stocks=1e6"
    evaluate gamma3 retired65-defined_benefits32e3-tax_free1e6 "-c $COUPLE_EVAL_FILE --master-age-start=65 --master-p-tax-free=1e6"

    wait
}

package com.gordoni.opal;

public class TargetResult
{
        public AAMap map;
        public double target;
        public double target_result;

        public TargetResult(AAMap map, double target, double target_result)
        {
                this.map = map;
                this.target = target;
                this.target_result = target_result;
        }
}

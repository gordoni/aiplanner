package com.gordoni.opal;

public class Linear_pf_scale extends Scale
{
        public Linear_pf_scale(double zero_buffer_size)
        {
                super(zero_buffer_size);
        }

        public double bucket_to_pf(int bucket)
        {
                return - bucket * zero_buffer_size;
        }

        public double pf_to_fractional_bucket(double pf)
        {
                return - pf / zero_buffer_size;
        }
}

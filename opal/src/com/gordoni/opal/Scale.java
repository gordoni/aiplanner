package com.gordoni.opal;

public abstract class Scale
{
        protected double zero_buffer_size;

        public Scale(double zero_buffer_size)
        {
                this.zero_buffer_size = zero_buffer_size;
        }

        public abstract double bucket_to_pf(int bucket);

        public abstract double pf_to_fractional_bucket(double pf);

        public int pf_to_bucket(double pf)
        {
                return pf_to_bucket(pf, "up");
        }

        public int pf_to_bucket(double pf, String dir)
        {
                double fractional_bucket = pf_to_fractional_bucket(pf);
                if (dir.equals("up"))
                        return (int) Math.ceil(fractional_bucket);
                else if (dir.equals("down"))
                        return (int) Math.floor(fractional_bucket);
                else
                        return (int) Math.floor(fractional_bucket + 0.5);
        }

        public static Scale scaleFactory(double zero_bucket_size, double scaling_factor)
        {
                if (scaling_factor == 1.0)
                        // Runs 15% faster by taking advantage of this special case.
                        return new Linear_pf_scale(zero_bucket_size);
                else
                        return new Exp_offset_scale(zero_bucket_size, scaling_factor);
        }
}

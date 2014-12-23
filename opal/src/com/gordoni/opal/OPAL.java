/*
 * AACalc - Asset Allocation Calculator
 * Copyright (C) 2009, 2011-2015 Gordon Irlam
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

package com.gordoni.opal;

import java.util.HashMap;
import java.util.Map;

public class OPAL
{
        public static void usage()
        {
                System.err.println("expecting: [-d] [-c C] [-e E]");
                System.exit(1);
        }

        public static void main(String[] args) throws Exception
        {
                Config config = new Config();
                HistReturns hist = new HistReturns();
                boolean daemon = false;
                boolean params_present = false;
                String param_filename = null;
                Map<String, Object> params = new HashMap<String, Object>();

                try
                {
                        for (int idx = 0; idx < args.length; idx++)
                        {
                                String arg = args[idx];
                                if ("-d".equals(arg))
                                        daemon = true;
                                else if ("-c".equals(arg))
                                        param_filename = args[++idx];
                                else if ("-e".equals(arg))
                                {
                                        config.load_params(params, args[++idx]);
                                        params_present = true;
                                }
                                else
                                {
                                        System.err.println("Unrecognized argument");
                                        usage();
                                }
                        }
                }
                catch (ArrayIndexOutOfBoundsException e)
                {
                        System.err.println("Invalid parameters");
                        usage();
                }

                if (daemon)
                {
                        assert(!params_present && param_filename == null);
                        OPALServerListen listen = new OPALServerListen(hist);
                        listen.run();
                }
                else
                {
                        String cwd = System.getProperty("user.dir");
                        new ScenarioSet(config, hist, cwd, params, param_filename);
                }
        }
}

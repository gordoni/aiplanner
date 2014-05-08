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
			BaseScenario scenario = new DefaultScenario(config, hist, cwd, params, param_filename);
			scenario.run_main();
		}
	}
}

package com.gordoni.opal;

import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;

public class OPALServerListen
{
        private HistReturns hist;

        private Object run_lock = new Object();

        public void run()
        {
                ServerSocket sock = null;
                try
                {
                        sock = new ServerSocket(8000); // InetAddress.getByName("localhost")
                                // Minimum backlog on Linux 3.2.0 appears to be 16, and connects possibly retry.
                                // Have to try something more tricky.  Namely place the connections in a queue, and close connections above the backlog.
                                // May need to test using multiple browsers rather than multiple browser windows for reasons that are not understood.
                }
                catch (Exception e)
                {
                        e.printStackTrace();
                        System.exit(1);
                }
                while (true)
                {
                        Socket conn = null;
                        try
                        {
                                conn = sock.accept();
                                try
                                {
                                        new Thread(new OPALServer(hist, run_lock, conn)).start();
                                }
                                catch (IllegalStateException e)
                                {
                                        try
                                        {
                                                conn.close();
                                        }
                                        catch (Exception e2)
                                        {
                                        }
                                }
                        }
                        catch (Exception e)
                        {
                        }
                }
        }

        public OPALServerListen(HistReturns hist)
        {
                this.hist = hist;
        }
}

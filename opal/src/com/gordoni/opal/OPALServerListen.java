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

import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;

public class OPALServerListen
{
        private HistReturns hist;
        private String opalhost;
        private String opalport;

        private Object run_lock = new Object();

        public void run()
        {
                ServerSocket sock = null;
                try
                {
                        if (opalhost.equals("*"))
                                sock = new ServerSocket(Integer.parseInt(opalport));
                        else
                                sock = new ServerSocket(Integer.parseInt(opalport), 0, InetAddress.getByName(opalhost));
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

        public OPALServerListen(HistReturns hist, String opalhost, String opalport)
        {
                this.hist = hist;
                this.opalhost = opalhost;
                this.opalport = opalport;
        }
}

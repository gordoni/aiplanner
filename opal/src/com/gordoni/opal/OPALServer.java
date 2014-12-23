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

import java.lang.Process;
import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.io.StringReader;
import java.net.Socket;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

public class OPALServer implements Runnable
{
        HistReturns hist;
        Object run_lock;
        Socket conn;

        public OPALServer(HistReturns hist, Object run_lock, Socket conn)
        {
                this.hist = hist;
                this.run_lock = run_lock;
                this.conn = conn;
        }

        public void run()
        {
                try
                {
                        BufferedReader in = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        OutputStream out = new BufferedOutputStream(conn.getOutputStream());
                        PrintStream pout = new PrintStream(out);
                        String request = in.readLine();
                        if (request == null)
                        {
                                return;
                        }
                        boolean cont = false;
                        Integer content_length = null;
                        String boundary = null;
                        while (true)
                        {
                                String line = in.readLine();
                                if (line == null || line.length() == 0)
                                        break;
                                if (line.toLowerCase().startsWith("content-length:"))
                                        content_length = Integer.parseInt(line.replaceAll(".*:\\s*", ""));
                                if (line.toLowerCase().startsWith("content-type:"))
                                        boundary = line.replaceAll(".*\\bboundary=(\\S+).*", "$1");
                                if (line.toLowerCase().matches("expect:\\s*100-continue"))
                                        cont = true;

                        }
                        if (content_length == null || boundary == null)
                                return;
                        String[] request_words = request.split(" ");
                        if (request_words.length < 2)
                        {
                                return;
                        }
                        String method = request_words[0];
                        String dirname = request_words[1];
                        if (!method.equals("POST") || !(dirname.startsWith("/home/ubuntu/oaa.data/static/results/") || dirname.equals("/home/ubuntu/oaa.data/static/sample")))
                        {
                                return;
                        }
                        if (cont)
                                pout.print("HTTP/1.1 100 Continue\r\n\r\n");
                        dirname = dirname.replaceAll("^.*/", "../run/");
                        File dir = new File(dirname);
                        dir.mkdirs();
                        char[] inBuf = new char[content_length];
                        int off = 0;
                        int recvd;
                        while ((recvd = in.read(inBuf, off, content_length - off)) > 0)
                        {
                                off += recvd;
                        }
                        BufferedReader mimeIn = new BufferedReader(new StringReader(new String(inBuf)));
                        String line = mimeIn.readLine();
                        while ((line = mimeIn.readLine()) != null)
                        {
                                String name = "none";
                                while (true)
                                {
                                        if (line.equals(""))
                                                break;
                                        else if (line.toLowerCase().startsWith("content-disposition:"))
                                        {
                                                name = line.replaceAll(".*\\bname=\"(.*?)\".*", "$1");
                                        }
                                        line = mimeIn.readLine();
                                }
                                StringBuilder sb = new StringBuilder();
                                while (!(line = mimeIn.readLine()).startsWith("--" + boundary))
                                {
                                        sb.append(line + "\n"); // Might corrupt binary data (\r\n), and appends a newline at the end of the file, but shouldn't matter for the data we are dealing with.
                                }
                                if (Arrays.asList("opal-scenario.txt", "plot.gnuplot").contains(name))
                                {
                                        PrintWriter fout = new PrintWriter(new File(dirname + "/" + name));
                                        fout.print(sb.toString());
                                        fout.close();
                                }
                        }
                        mimeIn.close();
                        try
                        {
                                //ByteArrayOutputStream mem = new ByteArrayOutputStream();
                                //PrintStream pmem = new PrintStream(mem);
                                //System.setOut(pmem);
                                PrintStream pstream = new PrintStream(new BufferedOutputStream(new FileOutputStream(new File(dirname + "/opal.log"))));
                                synchronized (run_lock)
                                {
                                        System.setOut(pstream);
                                        Map<String, Object> params = new HashMap<String, Object>();
                                        Config config = new Config();
                                        new ScenarioSet(config, hist, dirname, params, null);
                                }
                                pstream.close();
                                //pout.print(
                                //      "HTTP/1.1 200 OK\r\n" +
                                //      "Content-Type: text/plain\r\n" +
                                //      "Content-Length: " + mem.size() + "\r\n" +
                                //      "Connection: close\r\n\r\n");
                                //pout.write(mem.toByteArray(), 0, mem.size());
                                //mem.close();
                                pout.print(
                                         "HTTP/1.1 200 OK\r\n" +
                                         "MIME-Version: 1.0\r\n" +
                                         "Content-Type: multipart/mixed; boundary=" + boundary + "\r\n" +
                                         "Connection: close\r\n");
                                for (File file : dir.listFiles())
                                {
                                        String filename = file.getName();
                                        if (Arrays.asList("opal.log", "opal-number.csv", "opal-le.csv").contains(filename) || filename.endsWith(".png"))
                                        {
                                                pout.print(
                                                         "\r\n--" + boundary + "\r\n" +
                                                         "Content-Transfer-Encoding: binary\r\n" +
                                                         "Content-Disposition: attachment; filename=\"" + filename + "\"\r\n\r\n");
                                                FileInputStream dataStream = new FileInputStream(file);
                                                byte[] data = new byte[(int) file.length()];
                                                off = 0;
                                                while ((recvd = dataStream.read(data, off, data.length - off)) > 0)
                                                {
                                                        off += recvd;
                                                }
                                                dataStream.close();
                                                pout.write(data, 0, data.length);
                                        }
                                }
                                pout.print("\r\n--" + boundary + "--\r\n");

                        }
                        catch (Exception | AssertionError e)
                        {
                                e.printStackTrace();
                                pout.print(
                                        "HTTP/1.1 500 " + e + "\r\n" +
                                        "Connection: close\r\n\r\n");
                                e.printStackTrace(pout);
                        }
                        finally
                        {
                                out.flush();
                        }
                }
                catch (Exception e)
                {
                        e.printStackTrace();
                }
                finally
                {
                        try
                        {
                                conn.close();
                        }
                        catch (Exception e)
                        {
                        }
                }
                System.gc(); // Perform a GC now that the scenario has been released and while we are idling.
        }
}

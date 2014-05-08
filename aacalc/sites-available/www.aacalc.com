<VirtualHost *:80>
        ServerName www.aacalc.com
	Redirect permanent / https://www.aacalc.com/
</VirtualHost>

<VirtualHost *:80>
        ServerName aacalc.com
	Redirect permanent / https://www.aacalc.com/
</VirtualHost>

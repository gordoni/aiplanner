ServerName dev1.aacalc.com
	# Suppress FQDN warning.

<VirtualHost *:80>

	ServerName dev1.aacalc.com

	WSGIScriptAlias / /home/ubuntu/oaa/aacalc/django.wsgi

        Alias /static/ /home/ubuntu/oaa.data/static/

        AliasMatch ^/(favicon\.ico|robots\.txt)$ /home/ubuntu/oaa.data/static/$1

	<Directory />
                AuthType Basic
                AuthName "Development files restricted"
                AuthUserFile /home/ubuntu/oaa.data/oaa.htpasswd
                Require user opal
                Options -Indexes
                AllowOverride None
        </Directory>

	CustomLog ${APACHE_LOG_DIR}/access.log "%t %a %m %U %{Referer}i %s %T"

</VirtualHost>

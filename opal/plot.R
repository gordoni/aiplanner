#!/usr/bin/R --vanilla --slave -f

# Hack: change working directory to OPAL_USER_HOME so graphics files can be created (could also do by passing a function to options(device=...))
if (Sys.getenv('OPAL_USER_HOME') != '') {
    setwd(Sys.getenv('OPAL_USER_HOME'))
}

png(filename = 'opal-initial_aa.png', width=800, height=200, pointsize=20, bg='transparent')
par(mar=c(0,0,0,0))

data = read.table('opal-initial_aa.csv', header=TRUE, sep=',')
data = data[data$allocation>=0.005, ]
pie(data$allocation, labels=data$asset.class, col=rainbow(nrow(data)))

#!/usr/bin/R --vanilla --slave -f

file_prefix = Sys.getenv('OPAL_FILE_PREFIX')
if (file_prefix == '')
    file_prefix = 'opal'

png(filename = paste(file_prefix, '-initial_aa.png', sep=''), width=800, height=200, pointsize=20, bg='transparent')
par(mar=c(0,0,0,0))

data = read.table(paste(file_prefix, '-initial_aa.csv', sep=''), header=TRUE, sep=',')
data = data[data$allocation>=0.005, ]
pie(data$allocation, labels=data$asset.class, col=rainbow(nrow(data)))

#!/usr/bin/R --vanilla --slave -f

argv = commandArgs(trailingOnly = TRUE)
prefix = argv[1]

png(filename = paste(prefix, 'aa.png', sep=''), width=250, height=200, pointsize=12, bg='transparent')
par(mar=c(0,0,0,0))
data = read.table(paste(prefix, 'aa.csv', sep=''), header=TRUE, sep=',')
data = data[data$allocation>=0.005, ]
pie(data$allocation, labels=data$asset.class, col=rainbow(nrow(data)))

png(filename = paste(prefix, 'alloc.png', sep=''), width=600, height=200, pointsize=12, bg='transparent')
par(mar=c(2,0,0,0))
data = read.table(paste(prefix, 'alloc.csv', sep=''), header=TRUE, sep=',')
barplot(data$allocation, names.arg=data$class, axes=FALSE, space=0, col=rainbow(nrow(data)))

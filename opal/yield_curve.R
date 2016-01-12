#!/usr/bin/R --vanilla --slave -f

#if (Sys.getenv('OPAL_FILE_PREFIX') == '') {
#    file_prefix = './opal'
#} else {
#    file_prefix = paste(Sys.getenv('OPAL_FILE_PREFIX'), sep='')
#}

argv = commandArgs(trailingOnly = TRUE)
fname = argv[1]
date = argv[2]
outname = argv[3]

data = read.table(fname, sep=',')
x = data[1,2:ncol(data)]
y = data[data$V1==date,2:ncol(data)]

xout = seq(0, x[1,ncol(x)], 0.5)
s = spline(x, y, method='natural', xout=xout)

t = cbind(s$x, s$y)
colnames(t) = c('#years', 'real return')
write.table(t, outname, quote=FALSE, row.names=FALSE, sep=',')

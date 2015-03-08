#!/usr/bin/R --vanilla --slave -f

if (Sys.getenv('OPAL_FILE_PREFIX') == '') {
    file_prefix = './opal'
} else {
    file_prefix = paste(Sys.getenv('OPAL_FILE_PREFIX'), sep='')
}

#params = read.csv(paste(file_prefix, '-rcmt-params.csv', sep=''), colClasses=c('character'))
#  # R doesn't recognise 04/07/14 as a string, so force it to do so.
params = read.csv(paste(file_prefix, '-rcmt-params.csv', sep=''))
fname = as.character(params[1, 'file'])
date = as.character(params[1, 'date'])

data = read.table(fname, sep=',')
x = data[1,][2:ncol(data)]
y = data[data$V1==date,][2:ncol(data)]

xout = seq(0, 30, 0.5)
s = spline(x, y, method='natural', xout=xout)

t = cbind(s$x, s$y)
colnames(t) = c('#years', 'real return')
write.table(t, paste(file_prefix, '-rcmt.csv', sep=''), quote=FALSE, row.names=FALSE, sep=',')

#!/usr/bin/R --vanilla -f

# Based on: http://www.r-bloggers.com/introduction-to-asset-allocation/

file_prefix = Sys.getenv('OPAL_FILE_PREFIX')
if (file_prefix == '')
    file_prefix = 'opal'

# load Systematic Investor Toolbox
source(gzcon(file('sit.gz', 'rb')))

params = read.csv(paste(file_prefix, '-mvo-params.csv', sep=''))
ef_steps = params[1, 'ef_steps']
risk_tolerance = params[1, 'risk_tolerance']

hist.returns = read.csv(paste(file_prefix, '-mvo-returns.csv', sep=''))
symbols = colnames(hist.returns)
symbol.names = colnames(hist.returns)

bounds = read.csv(paste(file_prefix, '-mvo-bounds.csv', sep=''))

png(filename = paste(file_prefix, '-mvo-ef-%d.png', sep=''), width = 800, height = 400, pointsize = 20, bg = 'transparent')

# compute historical returns, risk, and correlation
ia = list()
ia$expected.return = apply(hist.returns, 2, mean, na.rm = T)
ia$risk = apply(hist.returns, 2, sd, na.rm = T)
ia$correlation = cor(hist.returns, use = 'complete.obs', method = 'pearson')

ia$symbols = symbols
ia$symbol.names = symbol.names
ia$n = length(symbols)
ia$hist.returns = hist.returns

# compute covariance matrix
ia$risk[ia$risk == 0] = 0.000001
ia$cov = ia$cor * (ia$risk %*% t(ia$risk))

# visualize input assumptions
#plot.ia(ia)  # Doesn't work for 2 asset classes.

# display each asset in the Risk - Return plot
#layout(1)
#par(mar = c(4,4,2,1), cex = 0.8)
#x = 100 * ia$risk
#y = 100 * ia$expected.return
#
#plot(x, y, xlim = range(c(0, x)), ylim = range(c(0, y)),
#	xlab='Risk', ylab='Return', main='Risk vs Return', col='black')
#grid();
#text(x, y, symbols,	col = 'blue', adj = c(1,1), cex = 0.8)



# Create Efficient Frontier
n = ia$n

# 0 <= x.i <= 1
#constraints = new.constraints(n, lb = 0, ub = 1)
constraints = new.constraints(n, lb = as.numeric(bounds[1, ]), ub = as.numeric(bounds[2, ]))

# SUM x.i = 1 ( total portfolio weight = 100%)
constraints = add.constraints(rep(1, n), 1, type = '=', constraints)

# Need to define and call the following function, or weird things happen.
# Don't understand why.
portopt(ia, constraints, ef_steps + 1, 'Portfolio')
portopt <- function
(
      ia,                             # Input Assumptions
      constraints = NULL,             # Constraints
      nportfolios = 50,               # Number of portfolios
      name = 'Risk',                  # Name
      min.risk.fn = min.risk.portfolio        # Risk Measure
)
{
}

# create efficient frontier consisting of 101 portfolios
nportfolios = ef_steps + 1

# set up output 
out = list(weight = matrix(NA, nportfolios, n))
colnames(out$weight) = ia$symbols		

# find minimum risk portfolio
out$weight[1, ] = min.risk.portfolio(ia, constraints)	

# find maximum return portfolio	
out$weight[nportfolios, ] = max.return.portfolio(ia, constraints)

# find points on efficient frontier
out$return = portfolio.return(out$weight, ia)
target = seq(out$return[1], out$return[nportfolios], length.out = nportfolios)

constraints = add.constraints(ia$expected.return, target[1], type = '=', constraints)
		
for(i in 2:(nportfolios - 1) ) {
	constraints$b[1] = target[i]
	out$weight[i, ] = min.risk.portfolio(ia, constraints)
}

# Zoom in on the region of the efficient frontier of interest.

# find maximum allowed risk portfolio
out$risk = portfolio.risk(out$weight, ia)
out$return = portfolio.return(out$weight, ia)
allowed.return = out$return[out$risk <= risk_tolerance]

if (len(allowed.return) <= 1) {

        out$weight = out$weight[rep(1, nportfolios), ]

} else {

	# find points on efficient frontier
	target = seq(out$return[1], tail(allowed.return, 1), length.out = nportfolios)

	# constraints = add.constraints(ia$expected.return, target[1], type = '=', constraints)
		
	for(i in 2:nportfolios ) {
	        constraints$b[1] = target[i]
	        out$weight[i, ] = min.risk.portfolio(ia, constraints)
	}

        if (is.na(out$weight[nportfolios, 1])) {
	        # NA due to computed return not quite being possible. Only happens if risk tolerance not reached.
	        out$weight[nportfolios, ] = max.return.portfolio(ia, constraints)
	}
}

# compute risk / return
out$risk = portfolio.risk(out$weight, ia)
out$return = portfolio.return(out$weight, ia)
out$name = 'Portfolio'

t = cbind(out$return, out$risk, out$weight)
colnames(t)[1] = 'return'
colnames(t)[2] = 'risk'
write.table(t, paste(file_prefix, '-mvo-ef.csv', sep=''), quote = FALSE, row.names = FALSE, sep = ',');

# plot efficient frontier
plot.ef(ia, list(out), layout = layout(1))

#ef$slope = (ef$return - risk.free) / ef$risk
#max.at = which.max(ef$slope)
#print(ia$expected.return)
#print(ia$risk)
#print(ef$return[max.at])
#print(ef$risk[max.at])
#print(ef$weight[max.at,])

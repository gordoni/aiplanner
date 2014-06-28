#!/usr/bin/gnuplot

set datafile separator ","
set terminal png transparent size 800,400 font "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
# Specify font path to work around Ubuntu 12.04 bug (warning message generated because unable to find font).

prefix = "`echo $OPAL_FILE_PREFIX`"
if (prefix eq "") prefix = "opal"

set xlabel "consumption ($)"
set xrange [0:consume]
set format x "%.1s%c"

unset ytics

set ylabel "utility"
set output prefix . "-utility-consume.png"
plot prefix . "-utility-consume.csv" using 1:2 with lines notitle

set ylabel "utility slope"
set yrange [0:1]
set output prefix . "-utility-slope-consume.png"
plot prefix . "-utility-consume.csv" using 1:(consume_slope_scale * $3) with lines notitle # Scale so last point is just visible.

set ylabel "slope'"
set format y "%g"
set yrange [*:*]
set output prefix . "-utility-slope2-consume.png"
plot prefix . "-utility-consume.csv" using 1:4 with lines notitle

set ytics

set ylabel "absolute risk aversion"
set format y "%g"
set yrange [0:consume_ara_max]
set output prefix . "-utility-ara-consume.png"
plot prefix . "-utility-consume.csv" using 1:(-$4/$3) with lines notitle

unset ytics

set xlabel "bequest ($)"
set xrange [0:tp]

set ylabel "utility"
set yrange [*:*]
if (bequest) set output prefix . "-utility-inherit.png"
if (bequest) plot prefix . "-utility-inherit.csv" using 1:2 with lines notitle

set ylabel "utility slope"
set yrange [0:*]
if (bequest) set output prefix . "-utility-slope-inherit.png"
if (bequest) plot prefix . "-utility-inherit.csv" using 1:3 with lines notitle

unset format

set xrange [0:*]
set format x "%.1s%c"
set ylabel "probability densitity"
set yrange [0:*]
unset ytics

set xlabel "portfolio size ($)"
if (paths) set output prefix . "-distrib-p.png"
if (paths) plot prefix . "-distrib-p.csv" using 1:2 with lines notitle

set xlabel "annual floor consumption ($)"
if (paths) set output prefix . "-distrib-floor.png"
if (paths) plot prefix . "-distrib-floor.csv" using 1:2 with lines notitle

set xlabel "annual upside consumption ($)"
if (paths) set output prefix . "-distrib-upside.png"
if (paths) plot prefix . "-distrib-upside.csv" using 1:2 with lines notitle

set xlabel "annual consumption ($)"
if (paths) set output prefix . "-distrib-consume.png"
if (paths) plot prefix . "-distrib-consume.csv" using 1:2 with lines notitle

set xlabel "inheritance ($)"
if (paths) set output prefix . "-distrib-inherit.png"
if (paths) plot prefix . "-distrib-inherit.csv" using 1:2 with lines notitle

set xrange [*:*]
set format x "%.0f%%"

set xlabel "annual change in portfolio size"
if (paths) set output prefix . "-distrib-change-p.png"
if (paths) plot prefix . "-distrib-change-p.csv" using ($1*100):2 with lines notitle

set xlabel "change in annual floor consumption"
if (paths) set output prefix . "-distrib-change-floor.png"
if (paths) plot prefix . "-distrib-change-floor.csv" using ($1*100):2 with lines notitle

set xlabel "change in annual upside consumption"
if (paths) set output prefix . "-distrib-change-upside.png"
if (paths) plot prefix . "-distrib-change-upside.csv" using ($1*100):2 with lines notitle

set xlabel "change in annual consumption"
if (paths) set output prefix . "-distrib-change-consume.png"
if (paths) plot prefix . "-distrib-change-consume.csv" using ($1*100):2 with lines notitle

set ytics

set ylabel "cummulative probability"
set yrange[0:100]
set format y "%.0f%%"

set xrange [0:*]
set format x "%.1s%c"

set xlabel "annual floor consumption ($)"
if (paths) set output prefix . "-distrib-floor-cdf.png"
if (paths) plot prefix . "-distrib-floor.csv" using 1:($3*100) with lines notitle

set xlabel "annual upside consumption ($)"
if (paths) set output prefix . "-distrib-upside-cdf.png"
if (paths) plot prefix . "-distrib-upside.csv" using 1:($3*100) with lines notitle

set xlabel "annual consumption ($)"
if (paths) set output prefix . "-distrib-consume-cdf.png"
if (paths) plot prefix . "-distrib-consume.csv" using 1:($3*100) with lines notitle

set xrange [*:*]
set format x "%.0f%%"

set xlabel "change in annual floor consumption"
if (paths) set output prefix . "-distrib-change-floor-cdf.png"
if (paths) plot prefix . "-distrib-change-floor.csv" using ($1*100):($3*100) with lines notitle

set xlabel "change in annual upside consumption"
if (paths) set output prefix . "-distrib-change-upside-cdf.png"
if (paths) plot prefix . "-distrib-change-upside.csv" using ($1*100):($3*100) with lines notitle

set xlabel "change in annual consumption"
if (paths) set output prefix . "-distrib-change-consume-cdf.png"
if (paths) plot prefix . "-distrib-change-consume.csv" using ($1*100):($3*100) with lines notitle

set xlabel "annual change in portfolio size"
if (paths) set output prefix . "-distrib-change-p-cdf.png"
if (paths) plot prefix . "-distrib-change-p.csv" using ($1*100):($3*100) with lines notitle

set xlabel age_label
set xrange [age_low:age_high]
set format x "%.0f"

set yrange [*:*]
set format y "%.0f%%"

set ylabel "change in annual consumption"
if (paths) set output prefix . "-pct-change-consume.png"
if (paths) plot prefix . "-pct-change-consume.csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent change in annual consumption"

set ylabel "annual change in portfolio size"
if (paths) set output prefix . "-pct-change-p.png"
if (paths) plot prefix . "-pct-change-p.csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent annual change in portfolio size"

set ylabel "portfolio size ($)"
set yrange [0:tp]
set format y "%.1s%c"

set palette defined (0.0 "blue", 50.0 "yellow", 100.0 "red")

set format cb "%.1s%c"

set cblabel "annual consumption ($)"
set cbrange [0:consume]
set output prefix . "-consume.png"
plot prefix . "-linear.csv" using 1:2:7 with image notitle

set cbrange [0:100]
set format cb "%.0f%%"

set cblabel "inflation-indexed SPIA purchase / total portfolio size"
if (annuitization > 0) set output prefix . "-ria.png"
if (annuitization > 0) plot prefix . "-linear.csv" using 1:2:($6 * 100) with image notitle

set cblabel "nominal SPIA purchase / total portfolio size"
if (annuitization > 0) set output prefix . "-nia.png"
if (annuitization > 0) plot prefix . "-linear.csv" using 1:2:($8 * 100) with image notitle

# Looping, introduced in Gnuplot 4.6, should make the following easier and cleaner.

set macros

symbol = word(asset_class_symbols, 1)
name = word(asset_class_names, 1)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 1) * 100) with image notitle

symbol = word(asset_class_symbols, 2)
name = word(asset_class_names, 2)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 2) * 100) with image notitle

symbol = word(asset_class_symbols, 3)
name = word(asset_class_names, 3)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 3) * 100) with image notitle

symbol = word(asset_class_symbols, 4)
name = word(asset_class_names, 4)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 4) * 100) with image notitle

symbol = word(asset_class_symbols, 5)
name = word(asset_class_names, 5)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 5) * 100) with image notitle

symbol = word(asset_class_symbols, 6)
name = word(asset_class_names, 6)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 6) * 100) with image notitle

symbol = word(asset_class_symbols, 7)
name = word(asset_class_names, 7)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 7) * 100) with image notitle

symbol = word(asset_class_symbols, 8)
name = word(asset_class_names, 8)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 8) * 100) with image notitle

symbol = word(asset_class_symbols, 9)
name = word(asset_class_names, 9)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 9) * 100) with image notitle

symbol = word(asset_class_symbols, 10)
name = word(asset_class_names, 10)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 10) * 100) with image notitle

symbol = word(asset_class_symbols, 11)
name = word(asset_class_names, 11)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 11) * 100) with image notitle

symbol = word(asset_class_symbols, 12)
name = word(asset_class_names, 12)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 12) * 100) with image notitle

symbol = word(asset_class_symbols, 13)
name = word(asset_class_names, 13)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 13) * 100) with image notitle

symbol = word(asset_class_symbols, 14)
name = word(asset_class_names, 14)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 14) * 100) with image notitle

symbol = word(asset_class_symbols, 15)
name = word(asset_class_names, 15)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 15) * 100) with image notitle

symbol = word(asset_class_symbols, 16)
name = word(asset_class_names, 16)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 16) * 100) with image notitle

symbol = word(asset_class_symbols, 17)
name = word(asset_class_names, 17)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 17) * 100) with image notitle

symbol = word(asset_class_symbols, 18)
name = word(asset_class_names, 18)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 18) * 100) with image notitle

symbol = word(asset_class_symbols, 19)
name = word(asset_class_names, 19)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 19) * 100) with image notitle

symbol = word(asset_class_symbols, 20)
name = word(asset_class_names, 20)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set cblabel name . " / investments"
if (symbol ne "") set output prefix . "-" . symbol . ".png"
if (symbol ne "") plot prefix . "-linear.csv" using 1:2:(column(8 + 20) * 100) with image notitle

symbol = word(asset_class_symbols, 21)
if (symbol ne "") die-invalid-command-too-many-asset_classes

if (paths) set output prefix . "-paths-p.png"
if (paths) plot prefix . "-paths.csv" using 1:2 with lines title "Sample portfolio size paths"

if (paths) set output prefix . "-pct-p.png"
if (paths) plot prefix . "-pct-p.csv" using 1:2:3:4 with errorlines title "95 percent portfolio size"

set ylabel "annual consumption ($)"
set yrange [0:consume]
if (paths) set output prefix . "-paths-consume.png"
if (paths) plot prefix . "-paths.csv" using 1:3 with lines title "Sample consumption paths"

if (paths) set output prefix . "-pct-consume.png"
if (paths) plot prefix . "-pct-consume.csv" using 1:2:3:4 with errorlines title "95 percent consumption"

set ylabel "annual payout ($)"
set yrange [0:annuity_payout]
if (paths && annuitization > 0) set output prefix . "-paths-ria.png"
if (paths && annuitization > 0) plot prefix . "-paths.csv" using 1:4 with lines title "Sample inflation-indexed SPIA paths"

if (paths && annuitization > 0) set output prefix . "-paths-nia.png"
if (paths && annuitization > 0) plot prefix . "-paths.csv" using 1:5 with lines title "Sample nominal SPIA paths"

set ylabel "annual annuitization amount ($)"
set yrange [0:annuitization]
if (paths && annuitization > 0) set output prefix . "-paths-ria_annuitization.png"
if (paths && annuitization > 0) plot prefix . "-paths.csv" using 1:6 with lines title "Sample inflation-indexed SPIA annuitization paths"

if (paths && annuitization > 0) set output prefix . "-paths-nia_annuitization.png"
if (paths && annuitization > 0) plot prefix . "-paths.csv" using 1:7 with lines title "Sample nominal SPIA annuitization paths"

set yrange [0:100]
set format y "%.0f%%"

symbol = word(asset_class_symbols, 1)
name = word(asset_class_names, 1)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 2)
name = word(asset_class_names, 2)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 3)
name = word(asset_class_names, 3)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 4)
name = word(asset_class_names, 4)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 5)
name = word(asset_class_names, 5)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 6)
name = word(asset_class_names, 6)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 7)
name = word(asset_class_names, 7)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 8)
name = word(asset_class_names, 8)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 9)
name = word(asset_class_names, 9)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 10)
name = word(asset_class_names, 10)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 11)
name = word(asset_class_names, 11)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 12)
name = word(asset_class_names, 12)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 13)
name = word(asset_class_names, 13)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 14)
name = word(asset_class_names, 14)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 15)
name = word(asset_class_names, 15)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 16)
name = word(asset_class_names, 16)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 17)
name = word(asset_class_names, 17)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 18)
name = word(asset_class_names, 18)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 19)
name = word(asset_class_names, 19)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 20)
name = word(asset_class_names, 20)
name_cmd = '"`echo ' . "'" . name . "'" . " | sed 's/_/ /g'" . '`"'
name = @name_cmd
set ylabel name . " / investments"
if (paths && symbol ne "") set output prefix . "-pct-" . symbol . ".png"
if (paths && symbol ne "") plot prefix . "-pct-" . symbol . ".csv" using 1:($2*100):($3*100):($4*100) with errorlines title "95 percent asset allocation"

symbol = word(asset_class_symbols, 21)
if (paths && symbol ne "") die-invalid-command-too-many-asset_classes

#set ylabel "inflation-indexed SPIA purchase / total portfolio size"
#set yrange [0:100]
#set format y "%.0f%%"
#if (annuitization > 0) set output prefix . "-average-ria.png"
#if (annuitization > 0) plot prefix . "-average.csv" using 1:($2 * 100) with lines notitle
#
#set ylabel "nominal SPIA purchase / total portfolio size"
#if (annuitization > 0) set output prefix . "-average-nia.png"
#if (annuitization > 0) plot prefix . "-average.csv" using 1:($3 * 100) with lines notitle
#
#set ylabel "small value / total portfolio size"
#set output prefix . "-average-sh.png"
#plot prefix . "-average.csv" using 1:((1 - ($2 + $3)) * $4 * 100) with lines notitle

set xlabel "maturity (years)"
set xrange [*:*]
set format x "%g"
set ylabel "annual return"
set yrange [*:*]
set format y "%.0f%%"
set output prefix . "-yield_curve.png"
plot prefix . "-yield_curve.csv" using 1:($2 * 100) with lines title "real", \
   prefix . "-yield_curve.csv" using 1:($3 * 100) with lines title "nominal"

set ylabel "SPIA price ($/$/year)"
set yrange [0:*]
set format y "%g"
if (annuitization > 0) set output prefix . "-annuity_price.png"
if (annuitization > 0) plot prefix . "-annuity_price.csv" using 1:2 with lines title "real actual 2014", \
  prefix . "-annuity_price.csv" using 1:3 with lines title "real modeled period", \
  prefix . "-annuity_price.csv" using 1:4 with lines title "real modeled cohort", \
  prefix . "-annuity_price.csv" using 1:5 with lines title "nominal actual 2014", \
  prefix . "-annuity_price.csv" using 1:6 with lines title "nominal modeled period", \
  prefix . "-annuity_price.csv" using 1:7 with lines title "nominal modeled cohort"

set xlabel "retirement number ($)"
set xrange [0:retirement_number_max]
set format x "%.1s%c"

set ylabel "failure probability"
set yrange [0:20]
set format y "%.0f%%"
if (retirement_number) set output prefix . "-rn-probability.png"
if (retirement_number) plot prefix . "-number.csv" using 1:($2 * 100) with lines notitle

set ylabel "failure length (years)"
set yrange [0:10]
set format y "%.0f"
if (retirement_number) set output prefix . "-rn-length.png"
if (retirement_number) plot prefix . "-number.csv" using 1:3 with lines notitle

set ylabel "equivalent guaranteed amount ($)"
set yrange [0:*]
set format y "%.1s%c"
if (retirement_number) set output prefix . "-rn-inverse-utility.png"
if (retirement_number) plot prefix . "-number.csv" using 1:4 with lines notitle

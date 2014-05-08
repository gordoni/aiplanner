asset_classes = (
    ('stocks',    'class_stocks',    'stocks',        1872, 2012),
    ('bonds',     'class_bonds',     'bonds',         1872, 2012),
    ('eafe',      'class_eafe',      'international', 1970, 2012),
    ('bl',        'class_ff_bl',     'big growth',    1927, 2012),
    ('bm',        'class_ff_bm',     'big neutral',   1927, 2012),
    ('bh',        'class_ff_bh',     'big value',     1927, 2012),
    ('sl',        'class_ff_sl',     'small growth',  1927, 2012),
    ('sm',        'class_ff_sm',     'small neutral', 1927, 2012),
    ('sh',        'class_ff_sh',     'small value',   1927, 2012),
    ('gs1',       'class_t1yr',      't-bill 1yr',    1954, 2012),
    ('cash',      'class_t1mo',      't-bill 1mo',    1927, 2012),
    ('reits',     'class_reits',     'real estate',   1972, 2012),
    ('gold',      'class_gold',      'gold',          1834, 2011),
    ('risk_free', 'class_risk_free', 'risk free',     1834, 2012),
)

def all_asset_classes():
    return tuple(asset_class for (_, asset_class, _, _, _) in asset_classes)

def asset_class_symbols(s):
    return tuple(symbol for (symbol, asset_class, _, _, _) in asset_classes if s[asset_class])

def asset_class_names(s):
    return tuple(name for (_, asset_class, name, _, _) in asset_classes if s[asset_class])

def asset_class_start(s):
    return max(start for (_, asset_class, _, start, _) in asset_classes if s[asset_class])

def asset_class_end(s):
    return min(end for (_, asset_class, _, _, end) in asset_classes if s[asset_class])

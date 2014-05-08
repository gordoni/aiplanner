asset_classes = (
    ('stocks',    'class_stocks',    'stocks',        1872, 2013),
    ('bonds',     'class_bonds',     'bonds',         1872, 2013),
    ('eafe',      'class_eafe',      'international', 1970, 2013),
    ('bl',        'class_ff_bl',     'large growth',  1927, 2013),
    ('bm',        'class_ff_bm',     'large neutral', 1927, 2013),
    ('bh',        'class_ff_bh',     'large value',   1927, 2013),
    ('sl',        'class_ff_sl',     'small growth',  1927, 2013),
    ('sm',        'class_ff_sm',     'small neutral', 1927, 2013),
    ('sh',        'class_ff_sh',     'small value',   1927, 2013),
    ('baa',       'class_baa',       'baa long corp', 1920, 2013),
    ('aaa',       'class_aaa',       'aaa long corp', 1920, 2013),
    ('gs10',      'class_t10yr',     't-note 10yr',   1872, 2013),
    ('gs1',       'class_t1yr',      't-bill 1yr',    1954, 2013),
    ('cash',      'class_t1mo',      't-bill 1mo',    1927, 2013),
    ('reits',     'class_reits',     'real estate',   1972, 2013),
    ('gold',      'class_gold',      'gold',          1872, 2013),
    ('risk_free', 'class_risk_free', 'risk free',     1872, 2013),
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

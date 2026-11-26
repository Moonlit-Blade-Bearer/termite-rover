print('$BEFORE_IMPORT')
try:
    import hw.start as s
    print('$IMPORT_OK', [a for a in dir(s) if not a.startswith('_')])
except Exception as e:
    print('$IMPORT_ERR', repr(e))
print('$AFTER_IMPORT')

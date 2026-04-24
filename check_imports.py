import glob, os, sys

files = sorted([p for p in glob.glob('*.py') if p != 'check_imports.py'])
ok = []
err = []
for p in files:
    name = os.path.splitext(p)[0]
    try:
        __import__(name)
        print('OK ', name)
        ok.append(name)
    except Exception as e:
        print('ERR', name, repr(e))
        err.append((name, repr(e)))

print('\nSUMMARY:')
print('OK:', ok)
print('ERR:', err)

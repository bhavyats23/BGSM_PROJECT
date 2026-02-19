f = open('app.py').read()

main_block = "if __name__ == '__main__':\n    app.run(debug=True, host='0.0.0.0', port=5000)"

# Remove all occurrences of the main block
f = f.replace(main_block, '')

# Remove any extra blank lines at end
f = f.rstrip()

# Add main block at very end
f = f + '\n\n' + main_block + '\n'

open('app.py', 'w').write(f)
print('Fixed! Routes after main block moved to correct position.')
print('Total routes:', f.count('@app.route'))
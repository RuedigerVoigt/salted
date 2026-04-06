# Using salted as a Python library

If you want to use `salted` not as a CLI script but as a Python library, a small script is all you need:

```python
import logging
import salted

# This displays all messages of level info or above on your screen.
# You could write the log output to a file.
logging.basicConfig(level=logging.INFO)

# Initializing salted by creating an object
linkcheck = salted.Salted()

# Now you can set parameters to specific values, for example:
linkcheck.timeout = 10

# Salted assumes all your files are in one folder or subfolders of that.
# Simply call the check function of the instance just created:
linkcheck.check('path_to_your_files/')
```

This starts the check. By default the results will be displayed on the command line interface you are using.
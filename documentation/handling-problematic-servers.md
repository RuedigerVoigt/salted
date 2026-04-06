# Handling problematic servers

Servers might block you if you send too many requests in a certain amount of time, then you should reduce the number of workers to slow salted down.

However, some servers block bots in general fearing automated access might be with malicious intent. This often includes link checkers although having working links pointing to their pages helps their SEO. Salted also mainly uses HEAD requests which do not load the full webpage, but only the headers. (Full requests are used as backup, but even then only a part is read.)

**Using Browser User Agents**

Some websites block user agents that do not match a browser. Salted provides easy-to-use presets:

```bash
# Use Chrome user agent (recommended)
salted -i ./homepage/ --user_agent chrome

# Use Firefox user agent
salted -i ./homepage/ --user_agent firefox

# Other presets: edge, safari, chrome-mac, chrome-linux
```

When using salted as a library:
```python
import salted

linkcheck = salted.Salted()

# Use a preset
linkcheck.user_agent = salted.get_user_agent('chrome')

linkcheck.check('./homepage/')
```
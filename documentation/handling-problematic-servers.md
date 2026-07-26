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

**Requests to internal addresses**

Salted checks the links it finds, and those come from the documents you point it at. Before each request — and again for every redirect it follows — it refuses targets that address the machine itself or a local network: loopback (`127.0.0.1`, `localhost`, `::1`), the private ranges (`10.x`, `172.16.x`, `192.168.x`), link-local addresses including the cloud metadata endpoint `169.254.169.254`, and the carrier-grade NAT range. Decimal and hexadecimal spellings of those addresses are recognized as well. Blocked targets are listed in the report as an exception.

This check reads the address written in the link; it does **not** look up host names. A name that points at an internal address — whether by intent or by accident — is therefore requested normally. Salted only records the status code, never the response body, so what such a link can reveal is limited to whether something answered. Still, if you check documents you do not control, run salted from a machine that has no access to internal services.
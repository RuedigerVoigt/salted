# Style the Output and Write to File

You can style the output using templates and can choose to write it to a file.

There are two builtin templates for salted:
* `default.cli.jinja`: formats the output for display on the command line interface.
* `default.md.jinja`: formats the output as markdown using the [pandoc syntax](https://pandoc.org/). This can easily be converted to other formats like .docx or PDF. (See the pandoc documentation for this.)

You can choose between those two templates by setting the parameter `template_name` to either of them.

The parameter `write_to` defaults to `cli` (command line interface). If you want to write the result to a file, set the value of `write_to` to the path of that file including the filename. Existing files will be overwritten.

The parameter `template_searchpath` defaults to `salted/templates`. This tells salted to use the builtin templates. If you want to use your own template, set this to the path **to the folder** on your file-system that has your template in it. Its name must be given with the `template_name` parameter!

Salted uses [Jinja2 templates](https://jinja.palletsprojects.com/en/2.11.x/).


The last optional parameter is `base_url`. Assume all your HTML files will be hosted on `www.example.com`. Salted does not know that. So if it finds a defect link it will tell you it is in `/home/youruser/path_to_your_folder/index.html`. If you set `base_url` to `https://www.example.com/` it will instead tell you the defect link is in `https://www.example.com/index.html`.
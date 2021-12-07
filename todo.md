## Recognizing Special Columns
They're stated but unused. Making sure all configuration options are respected is important.

## Make Command Line Script and Arguements
Doing this might require making a package,
which will also improve organization.
Important flags include -h for help, -o for output location, -c for config location, -i for input file or directory, -v to validate google maps key in config.

## Caching converted coordinates
This will prevent API calls from being wasted by creating a small database
to store them. It should support sqlite or json.

## Export as EXE
Will make the script extremely easy to run on other machines, albeit somewhat slow.
This is a fair tradeoff.
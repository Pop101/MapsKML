The settings file needs to be customized to your specifications.
Especially the desired place description
I recommend using a json editor such as https://jsoneditoronline.org/

Later values overwrite earlier values.
Be especially careful with the style section with your short patterns.

The most important thing is getting a Google Maps API Key
Follow this tutorial https://www.youtube.com/watch?v=Szv0p9eyRX0
Paste it in the settings.
Don't forget to modify settings to fit your needs

The script is a python script, so to run it, you need to install python.
After getting python 3 or later, check your version
by typing "python -version" into the command line.

Open this folder in a command prompt and type
"pip3 install -r requirements.txt" to install required packages,
then paste your csv into the folder.
Run the script with "python3 parsecsv.py" and your kml will pop out.
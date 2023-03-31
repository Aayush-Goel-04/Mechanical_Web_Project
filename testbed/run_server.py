import sys

# sys.path.insert(0, '/var/www/ME/')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")

from flaskapp import app

if __name__ == '__main__':

    # Start App
    app.run(debug=True)
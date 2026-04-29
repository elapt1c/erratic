# ERRATIC C2 
Python based C2 server based on socketio and http/s

HOW TO INSTALL
Ensure you have python3.8+, make an issue if you have any problems with this software.

Get and enter the repo:
`git clone https://github.com/elapt1c/erratic.git`
`cd erratic`

Install all required python packages (on the server side)
`pip install -r requirements.txt`

Configure the `config.yml` file (VERY IMPORTANT FOR NON-LOCAL) to your liking.
Then simply run the server application:
`python3 main.py`

And it should be good to go! based on your config.yml, it will edit the payload response.
`http://x.x.x.x:xxxx/payload` will give you a python file for the clients. as long as this is running and it is set up correctly, the client will contact the server and give you control.
I suggest you compile it with nuitka and MSVC to give it the lowest possible detection rating on antivirus.
if you go to `http://x.x.x.x:xxxx/` you will be able to access the WebUi and login with the credentials you set in config.yml.

If possible, try to run the c2 through https to ensure security.

# THE LAUNCHER:
I created a ready-to-go exe-based launcher for your c2 servers. all you need to do is download the zip file, alter the config.txt's contents to be `http://x.x.x.x:xxxx/payload` (replace with your actual c2 server's ip)
then on the victim's machine, unzip the folder and run the exe and it will connect to your c2 server.


# LOOKING FOR CONTRIBUTERS:
for bug fixes and features, open a pull request.
if you have any issue using erratic, open an issue and i will try to get to you when i can.

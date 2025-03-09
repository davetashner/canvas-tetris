A very simple HTML5 version of Tetris, for educational purposes, made in 45 minutes.

Watch the making-of timelapse:
http://www.youtube.com/watch?v=GQTZ_TPxJhM

Play:
https://dionyziz.com/graphics/canvas-tetris/

**setup-tetris-server.py Organization**

Tetris Cloud Server Deployment

The setup-tetris-server.py script automates the deployment of a Tetris web game on an AWS EC2 instance with a custom DNS name and SSL certificate.

*Features*

✅ Deploys a Tetris game to an AWS EC2 instance.

✅ Uses a custom subdomain (e.g., tetris.mydomain.com).

✅ Configures HTTPS with Let’s Encrypt SSL.

✅ Creates necessary AWS resources:

	•	Security group
	•	IAM role with S3 read permissions
	•	Route 53 DNS record

✅ Waits for DNS propagation and SSL activation.

Prerequisites
	•	AWS CLI configured with the required credentials.

	•	A Route 53 hosted zone for managing the DNS records.

	•	A valid public domain (e.g., mydomain.com).

Potential Improvements:

	1.	Reduce Redundant Code
	•	Functions such as wait_for_instance_profile() and create_iam_role() include multiple nested checks for IAM entities. Some parts can be refactored into reusable utilities.
	
    2.	Enhanced Logging
	•	More structured output (e.g., success messages, status updates) can improve debugging and user experience.
	
    3.	Configurable Parameters
	•	Some hardcoded values like REGION, INSTANCE_TYPE, and HOSTED_ZONE_ID could be configurable via a .env file or command-line options.


Usage

1️⃣ Basic Deployment

python3 setup-tetris-server.py --dns my-tetris

This will:
	•	Launch a Tetris server at my-tetris.mydomain.com
	•	Configure SSL via Let’s Encrypt.
	•	Automatically update the Route 53 DNS record.

2️⃣ Test Only DNS Health Check

If you only want to test whether the DNS has propagated:

python3 setup-tetris-server.py --dns my-tetris --test-dns

How It Works
	1.	Fetches the latest Ubuntu AMI.
	2.	Creates an EC2 instance with:
	•	A security group allowing HTTP and HTTPS access from the Internet.
	3.	Bootstraps the instance with:
	•	Tetris installation (cloned from GitHub).
	•	Nginx configuration to serve the game.
	•	Let’s Encrypt SSL setup.
	4.	Waits for DNS propagation before finalizing.
	5.	Outputs the public URL once ready.

Example Output

Fetching latest Ubuntu AMI...
Using latest Ubuntu AMI: ami-0abc123xyz
Creating security group...
Security group tetris-sg configured.
Launching EC2 instance...
EC2 Instance launched with ID: i-0123456789abcdef0
Waiting for DNS propagation...
✅ DNS resolved: my-tetris.mydomain.com -> 3.15.27.5
Requesting SSL certificate...
✅ SSL activated! Access Tetris at: https://tetris.mydomain.com

Troubleshooting

1️⃣ If the DNS check fails:
	•	Wait a few minutes and re-run with --test-dns.
	•	Ensure your Route 53 hosted zone is properly configured.

2️⃣ If SSL setup fails:
	•	Check if the server is reachable via HTTP before retrying.

3️⃣ To manually check the server status:

curl -I https://tetris.mydomain.com

Future Improvements

🔹 Add auto-scaling support for handling high traffic.
🔹 Store configurations in a .env file for better customization.
🔹 Improve logging output for better debugging.

License
=======
This version of tetris is MIT licensed:

Copyright (C) 2012 Dionysis "dionyziz" Zindros <dionyziz@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

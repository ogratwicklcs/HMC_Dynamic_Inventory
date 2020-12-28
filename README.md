# HMC_Dynamic_Inventory

**OVERVIEW**

This python script is designed to output all LPARs from the IBM HMC console in JSON format.  This JSON output can be used as a inventory source for Ansible to run playbooks.  

Currently the script will only create a single group called ```lpars``` and within that group it will populate all of the LPARs found within your HMC.  Additionally for each LPAR found the script will assign the variable ```ansible_host``` with the value of the IP of the LPAR, if no IP is found it will assign the lpar name for the ```ansible_host``` value.

**CONFIGURATION**
All connection information is passed through envrionment variables.  Below are the envrionment variables that will need to be set: <br />

```hmchostname``` - The ip/hostname of the HMC API endpoint <br />
```hmc_port``` - The port the API is accessible from (defaults to 443) <br />
```hmcuser``` - The username to login <br />
```hmcpassword``` - The password for the user you are logging in as <br />
```verify_ssl``` - Whether you want to verify the SSL connection to the endpoint (if not set, defaults to false) <br />


Python Libraries requires - <br />
xmltodict <br />
json <br />
urllib3 <br />
requests <br />
argparse <br />
socket <br />

from libs import connected_apps, tableau_rest

def update(env_dict, workbook_id):
  # encode a JWT token for connected apps authentication: https://help.tableau.com/current/online/en-us/connected_apps.htm#step-4-embedding-next-steps
  jwt = connected_apps.encode(env_dict)

  # authenticate to Tableau's REST API
  api_key = tableau_rest.auth(env_dict, jwt)

  # get all broadcasts on the site
  broadcasts = tableau_rest.get_broadcasts(api_key)

  # update the broadcast
  tableau_rest.update_broadcast(api_key, broadcasts, workbook_id, False, False)
  
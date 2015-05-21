'''
Created on May 19, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import other_response as oresp
from controllers.utils import err
from controllers.utils import authenticate
from controllers.errors import AuthenticationError

class Authentication(View):
    '''
    Handles the authentication requests of the site.
    '''
    
    def post(self, request, *args, **kwargs):
        '''
        Log the person in. Login requires the following json to work:
        
            {
                "email" : "<email>",
                "password" : "<password>"
            }
        '''
        try:
            session_id = authenticate(request)
            resp = oresp(request)
            resp.set_cookie("sessionid", session_id)
            return resp
        except (KeyError, ValueError) as e:
            return err(e)
        except AuthenticationError as ae:
            return err(ae, 401)
        
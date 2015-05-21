'''
Created on May 19, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import other_response as oresp
from controllers.utils import response as resp
from controllers.utils import err
from controllers.utils import authenticate
from controllers.errors import AuthenticationError
from json import loads as load
from controllers.utils import read
from db.models import Poster as User
from django.db.utils import IntegrityError
from django.contrib.auth import logout

class Poster(View):
    '''
    The class that handles the poster objects.
    '''
    
    def post(self, request, *args, **kwargs):
        '''
        Creates a new poster. The poster object should be of the following json type:
        
            {
                "email" : "<email>",
                "password" : "<password>"
            }
        '''
        j = load(read(request))
        try:
            p = User.objects.create_user(**j)
            return resp(request, (p,))
        except IntegrityError as ie:
            return err(ie)

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
            resp.set_cookie("sessionid", session_id, max_age=30)
            return resp
        except (KeyError, ValueError) as e:
            return err(e)
        except AuthenticationError as ae:
            return err(ae, 401)
    
    def delete(self, request, *args, **kwargs):
        '''
        Log the person out. Logout requires nothing but the cookie to work. Will always return 204.
        ''' 
        logout(request)
        return oresp(request) 
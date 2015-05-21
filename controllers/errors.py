'''
Created on May 21, 2015

@author: derigible
'''

class AuthenticationError(Exception):
    
    def __init__(self):
        super(AuthenticationError, self).__init__("Authentication error. Username/password combination not found.")
'''
Created on May 18, 2015

@author: derigible
'''
from django.http.response import HttpResponse
from django.core import serializers as sz
from django.contrib.auth import login, SESSION_KEY
from .errors import AuthenticationError
from db.models import Poster
import json

def set_headers(response, headers):
    '''
    Set a dictionary of headers to the HttpResponse object.
    
    @param response: the HttpResponse
    @param headers: the headers dictionary
    '''
    for key, val in headers.items:
        setattr(response, key, val)

def response(request, qs, headers = {}):
    '''
    Returns a response according to the type of request made. This is done by passing in the 
    Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
    to json. This is a utility for serializing objects.
    
    @param request: the request object
    @param qs: an iterable of model objects
    @param headers: a dictionary of headers to add
    @return the HttpResponse object
    '''
    accept = request.META.get('HTTP_ACCEPT', 'application/json')
    if 'xml' in accept:
        data = sz.serialize("xml", qs)
        ct = "application/xml"
    else: #defaults to json if nothing else is found of appropriate use
        data = sz.serialize("json", qs)
        ct = "application/json"
    resp = HttpResponse(data, content_type = ct)
    if headers:
        set_headers(resp, headers)
    return resp

def other_response(request, data = None, headers = {}):
    '''
    Returns a response according to the type of request made. This is done by passing in the 
    Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
    to json. Data should already be formatted in the correct Content-Type. This is a utility for sending all other responses.
    
    @param request: the request object
    @param data: the data to send; if None will send nothing with status 204
    @return the HttpResponse object
    '''
    accept = request.META.get('HTTP_ACCEPT', 'application/json')
    if data is not None:
        if 'xml' in accept:
            ct = "application/xml"
        else: #defaults to json if nothing else is found of appropriate use
            ct = "application/json"
        status = 200
    else:
        data = ""
        ct = None
        status = 204
    resp = HttpResponse(data, content_type = ct, status = status)
    if headers:
        set_headers(resp, headers)
    return resp

def err(msg, status = 400):
    '''
    Send an error response.
    
    @param msg: the reason for the error
    @param status: the status code of the error
    @return the HttpResponse object
    '''
    resp = HttpResponse('{{"err" : "{}"}}'.format(msg), content_type = "application/json", status = status)
    resp.reason_phrase = msg
    return resp

def authenticated(func):
    '''
    A decorator to check if the user is authenticated. Since it is undesirable in an api to redirect to a login, this
    was made to replace the requires_login django decorator. This should be wrapped in method_decorator if a class-based
    view.
    
    @param func: the view function that needs to have an authenticated user
    @return the response of the function if authenticated, or an error response
    '''
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated():
            return func(request, *args, **kwargs)
        return HttpResponse('{"err" : "Unauthenticated."}', content_type = "application/json", status = 401)
    return wrapper

def read(request):
    '''
    Read and decode the payload.
    
    @param request: the request object to read
    @return the decoded request payload
    '''
    return request.read().decode('utf-8')

def authenticate(request, email = None, password = None):
    '''
    Log the Poster in or raise an Unauthenticated error. If email or password is None, will attempt to extract from the
    request object. This assumes it is a json object. If other formats are used, you must pass in email and password
    separately.
    
    @param request: the request to log in
    @param email: the email of the poster
    @param password: the password of the poster
    @return the sessionid, the user object
    '''
    if email is None or password is None:
        try:
            j = json.loads(read(request))
            email = j["email"]
            password = j["password"]
        except ValueError:
            raise ValueError("Faulty json. Could not parse.")
        except KeyError as ke:
            KeyError(ke)
    login(request, None)
    user = Poster.objects.get(email = email)
    if not user.check_password(password):
        raise AuthenticationError()
    
    return request[SESSION_KEY]
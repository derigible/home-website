'''
Created on May 18, 2015

@author: derigible
'''
from django.http.response import HttpResponse
from django.core import serializers as sz

def response(request, qs):
    '''
    Returns a response according to the type of request made. This is done by passing in the 
    Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
    to json.
    '''
    accept = request.META.get('HTTP_ACCEPT', 'json')
    print(accept)
    if 'xml' in accept:
        data = sz.serialize("xml", qs)
        ct = "application/xml"
    else: #defaults to json if nothing else is found of appropriate use
        data = sz.serialize("json", qs)
        ct = "application/json"
    return HttpResponse(data, content_type = ct)
"""
Created on Jul 2, 2015

@author: derigible

An attempt to combine views with a manager without having to write any extra
code. This is to make writing REST applications much simpler as it will
treat each table as if it is a returnable entity. The beauty of this setup
is that since it is a Django manager it can still be referenced by other 
Django models. This only adds some automatic support to the manager, nothing
more.
"""

from json import loads as load
from sys import modules as mod

from django.db import models as m
from django.views.generic.base import View
from django.http.response import HttpResponse
from django.core import serializers as sz


class ViewWrapper(View):
    """
    A wrapper to ensure that the view class never gets positional arguments so
    as to make it work with being combined with Models.
    """
    
    def __init__(self, *args, **kwargs):
        super(ViewWrapper, self).__init__(**kwargs)

class ModelAsView(m.Model, ViewWrapper):
    register_route = False
    model_name = None   
    
    @property
    def model(self):
        if self.__class__ is None:
            raise AttributeError("model_name is None. You must provide a model_name attribute for your model.")
        if not hasattr(self, "__model"):
            print(self.__class___name)
            self.__model = mod[self.__class__]
            self.__model = self.__model()
        print(self.__model, type(self.__model))
        return self.__model
    
    def _get_qs(self, request, *args, **kwargs):
        '''
        A helper method to get the queryset, to be used for GET, PUT, and maybe DELETE. Look at the
        GET docs to see how this works.
        '''
        print(self.__class__)
        args = args[0].split('/')[:-1]
        if not args:
            qs = self.__class__.objects.all()
            if "ids" in request.GET:
                ids = request.GET.get('ids').split(',')
                qs = qs.filter(id__in = ids)
            reqDict = {field : request.GET[field] for field in self.__class__._meta.get_all_field_names() if field in request.GET}
            return qs.filter(**reqDict)      
        elif len(args) == 1:
            return self.__class__.objects.filter(id = args[0])
        else:
            reqDict = {field : request.GET[field] for field in self.__class__._meta.get_all_field_names() if field in request.GET}
            return self.__class__.objects.filter(id__in = args, **reqDict)
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/3/4/.../ 
            3) add the query param ids as a csv for those entities by id you want: ids=1,2,3,4,...
                
        Note that the query params need to match the name of the manager fields in order to work.
        '''
        print(request, args, kwargs)
        qs = self._get_qs(request, *args, **kwargs)
        if request.GET.get("expand", False):
            qs = qs.select_related().prefetch_related()
        return self.response(request, qs)
    
    def post(self, request, *args, **kwargs):
        '''
        The post currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "<m2m>" : [
                <m2m_id>,...
            ]
        }
        '''
        j = load(self.read(request))
        bp = self.__class__.objects.create(user = request.user, **j["data"])
        if len(j) > 1: #there are many2many fields to add, lets add them
            for m2m in self.m2ms: #Get the name of the m2m used
                if m2m in j and type(j.get(m2m) == list):
                    bp.labels.add(*j[m2m])
        return self.response(request, (bp,))
    
    def put(self, request, *args, **kwargs):
        '''
        The put currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "add_<m2m>" : [
                <m2m_id>,...
            ],
            "delete_<m2m>" : [
                <m2m_id>,...
            ]
        }
        
        Note that you can update from a queryset relative to the rules of a get. Meaning you 
        can search for a set of entities to update at once.
        '''
        j = load(self.read(request))
        qs = self._get_qs(request, *args, **kwargs)
        entity = qs.update(**j["data"])
        if len(j) > 1: #there are many2many fields to add and delete, lets add them
            for m2m in self.m2ms:
                if "add_" + m2m in j and type(j.get(m2m), list):
                    entity.labels.add(*j[m2m])
                if "delete_" + m2m in j and type(j.get(m2m), list):
                    entity.labels.remove(*j[m2m])
        return self.other_response(request)
    
    def delete(self, request, *args, **kwargs):
        '''
        Delete an entity. This is a no payload endpoint where you can delete either in bulk by adding
        doing one of the three things:
        
            1) a single entity: .../entity/<id>/ where you just add one id in the path
            2) multiple entities: .../entity/<id>/<id2>/.../ where you add as many ids as you want in the path
            3) leave the args blank and add query param with at least one query param called ids as follows:
                
                    ids=1,2,3,4,5
                    
                note that the ids are a csv.
                
            Note that the GET argument can also be used to help narrow down from the list of ids those that
            contain other query attributes. Note that these query attributes need to have the names of the manager
            fields, just like in getting objects.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            if "ids" not in request.GET:
                return self.err("Did not contain any valid ids to delete.")
            ids = request.GET.get("ids").split(',')
            reqDict = {field : request.GET[field] for field in self.__class__._meta.get_all_field_names() if field in request.GET}
            deletes = self.__class__.objects.filter(id__in = ids, **reqDict)
        elif len(args) == 1:
            deletes = self.__class__.objects.get(id = args[0])
        else:
            deletes = self.__class__.objects.filter(id__in = args)
        
        deletes.delete()
        
        return self.other_response(request)
    
    def set_headers(self, response, headers):
        '''
        Set a dictionary of headers to the HttpResponse object.
        
        @param response: the HttpResponse
        @param headers: the headers dictionary
        '''
        for key, val in headers.items:
            setattr(response, key, val)
    
    def response(self, request, qs, headers = {}, fields = []):
        '''
        Returns a response according to the type of request made. This is done by passing in the 
        Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
        to json. This is a utility for serializing objects.
        
        If the query param single=true is found, then will return a single object if the queryset returns only
        one object. Otherwise all queries are sent in a list by default. This option is only available for json.
        
        @param request: the request object
        @param qs: an iterable of manager objects
        @param headers: a dictionary of headers to add
        @param fields: a list of fields to include
        @return the HttpResponse object
        '''
        accept = request.META.get('HTTP_ACCEPT', 'application/json')
        is_single = len(qs) == 1
        if 'xml' in accept:
            if not fields:
                data = sz.serialize("xml", qs)
            else:
                data = sz.serialize("xml", qs, fields = fields)
            ct = "application/xml"
        else: #defaults to json if nothing else is found of appropriate use
            if not fields:
                data = sz.serialize("json", qs)
            else:
                data = sz.serialize("json", qs, fields = fields)
            data = data[1:-1] if is_single and request.GET.get("single", "false").lower() == "true" else data
            ct = "application/json"
        resp = HttpResponse(data, content_type = ct)
        if headers:
            self.set_headers(resp, headers)
        return resp
    
    def other_response(self, request, data = None, headers = {}):
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
            self.set_headers(resp, headers)
        return resp
    
    def err(self, msg, status = 400):
        '''
        Send an error response.
        
        @param msg: the reason for the error
        @param status: the status code of the error
        @return the HttpResponse object
        '''
        resp = HttpResponse('{{"err" : "{}"}}'.format(msg), content_type = "application/json", status = status)
        resp.reason_phrase = msg
        return resp
    
    def read(self, request):
        '''
        Read and decode the payload.
        
        @param request: the request object to read
        @return the decoded request payload
        '''
        return request.read().decode('utf-8')
    
    class Meta:
        abstract = True
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

from django.db import models as m
from django.views.generic.base import View
from django.http.response import HttpResponse
from django.core import serializers as sz
from django.contrib.auth.models import AbstractBaseUser

from .serializer import serialize


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
    
def read(request):
    '''
    Read and decode the payload.
    
    @param request: the request object to read
    @return the decoded request payload
    '''
    d = request.read()
    if d:
        try:
            d = load(d.decode('utf-8'))
        except ValueError as e:
            raise ValueError("Not a valid json object: {}".format(e))
    return d

class ViewWrapper(View):
    """
    A wrapper to ensure that the view class never gets positional arguments so
    as to make it work with being combined with Models.
    """
    register_route = False
    def __init__(self, *args, **kwargs):
        super(ViewWrapper, self).__init__(**kwargs)
        
    def dispatch(self, request, *args, **kwargs):
        #It makes sense why these are stored in the request, but i want them
        #in the view for convenience purposes
        self.accept = request.META.get('HTTP_ACCEPT', 'application/json')
        self.params = request.GET
        self.fields = [f for f in self.params.get('_fields', "").split(',') 
                       if f in self.field_names]
        self.expand = '_expand' in self.params
        self.sdepth = int(self.params['_depth']) if self.params.get('_depth', None) is not None and self.params.get('_depth', None).isdigit() else 0
        try:
            self.data = read(request)
        except ValueError as e:
            return err(e)
        return super(ViewWrapper, self).dispatch(request, *args, **kwargs)

class BaseModelWrapper():
    """
    A wrapper to help define what a model wrapper will need. This is necessary
    since the AbstractBaseUser model is a model already and you can't sublass
    from two models. Or something like that.
    """
    
    def delete_entity(self, *args, **kwargs):
        raise NotImplementedError("This had not been implemented.")
    
class ModelWrapper(BaseModelWrapper, m.Model):
    """
    A wrapper to ensure that the model class does not get called when a DELETE
    method is sent. To delete a model, call the delete_entity method.
    """
    
    def delete_entity(self, *args, **kwargs):
        """
        Call this method to delete a model instance.
        """
        super(ModelWrapper, self).delete(*args, **kwargs)
        
    class Meta:
        abstract = True
        
class ABUWrapper(BaseModelWrapper, AbstractBaseUser):
    """
    A wrapper to ensure that the user model does not get called when a DELETE
    method is sent. To delete a user, call the delete_entity method.
    """
    
    def delete_entity(self, *args, **kwargs):
        """
        Call this method to delete a model instance.
        """
        super(ABUWrapper, self).delete(*args, **kwargs)
        
    class Meta:
        abstract = True

class BaseModelAsView(BaseModelWrapper, ViewWrapper):
    """
    A base class that should inherit this first, then a Modelwrapper, than a
    ViewWrapper.
    """
    
    @property
    def m2ms(self):
        if not hasattr(self, "_m2ms"):
            self._m2ms = [str(m2m[0]).split('.')[-1] for m2m in self.__class__._meta.get_m2m_with_model()]
        return self._m2ms
    
    @property
    def fks(self):
        print(self._meta.get_all_related_objects())
        print(self.field_names)
        if not hasattr(self, "_fks"):
            self._fks = [str(fk).split('.')[-1] for fk in self.field_names if getattr(self._meta.get_field_by_name(fk)[0], "foreign_key", False)]
        return self._fks
        
    @property
    def field_names(self):
        if not hasattr(self, "_field_names"):
            self._field_names = self.__class__._meta.get_all_field_names()
        return self._field_names
        
    def _get_qs(self, *args, **kwargs):
        '''
        A helper method to get the queryset, to be used for GET, PUT, and maybe DELETE. Look at the
        GET docs to see how this works.
        '''
        def filter_by_pks(vals):
            for f in self.field_names:
                if getattr(self._meta.get_field_by_name(f)[0], "primary_key", False):
                    return {f + "__in" : vals}
            else:
                return {}
        args = args[0].split('/')[:-1]
        if "ids" in self.params:
            args += self.params.get('ids').split(',')
        filtered = self.__class__.objects.all()
        if len(args) == 1 and 'id' in self.field_names:
            filtered = filtered.filter(id = args[0])
        elif 'id' in self.field_names and args:
            filtered = filtered.filter(id__in = args)
        elif args:
            filtered = filtered.filter(**filter_by_pks(args))            
        if self.fields:
            if self.expand:
                filtered.only(*self.fields)
            else:
                filtered.values(*self.fields)
        reqDict = {field : self.params[field] for field in self.field_names if field in self.params} 
        return filtered.filter(**reqDict)
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/3/4/.../ 
            3) add the query param ids as a csv for those entities by id you want: ids=1,2,3,4,...
                
        Note that the query params need to match the name of the manager fields in order to work.
        
        You may also pass in other filtering criteria by adding the key,value pair of a field
        you wish to filter on. For example:
        
            name=Bob
            
        If there is a name field on the entity, will filter by the name Bob. Adding fields
        that are not present on the entity does nothing. If you pass in the filter name=Bob
        and no ids, will search only on that field. 
        
        A query with no filter will return the entirety of that entity's table. If you pass
        in the keyword _expand, will get the objects related to this entity as well and
        place them in the corresponding entity's object under a list with the name
        of the m2m field as identifier.
        
        If the query _fields is passed in as a csv of desired fields, will attempt to retrieve only those
        fields requested, otherwise all fields are returned.
        
        If the _depth field is included with a valid number, 
        '''
        qs = self._get_qs(*args, **kwargs)
        if self.expand:
            qs = qs.select_related().prefetch_related()
        else:
            qs = qs.values()
        return self.response(qs)
    
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
        
        If your model requires that the user is registered on create, then
        add the register_user_on_create = <user_model_field_name> where the
        value is the name of the field the user model is in. 
        '''
        user_field_name = getattr(self, 'register_user_on_create', '')
        if user_field_name:
            self.data["data"][user_field_name] = request.user
        bp = self.__class__.objects.create(**self.data["data"])
        if len(self.data) > 1: #there are many2many fields to add, lets add them
            for m2m in self.m2ms:
                if m2m in self.data and type(self.data.get(m2m)) == list:
                    getattr(bp, m2m).add(*self.data[m2m])
        self.expand = True
        return self.response((bp,))
    
    def put(self, request, *args, **kwargs):
        '''
        The put currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "<m2m>" : {
                "add" : [ .... ],
                "delete" : [ .... ]
            }
        }
        
        Note that you can update from a queryset relative to the rules of a get. Meaning you 
        can search for a set of entities to update at once.
        
        Filtering is done in the same way as GET.
        '''
        qs = self._get_qs(*args, **kwargs)
        if len(qs) > 1:
            return err("Can only update one entity at a time.")
        qs.update(**self.data["data"])
        if len(self.data) > 1: #there are many2many fields to add and delete, lets add them
            for m2m in self.m2ms:
                print(m2m)
                if m2m in self.data:
                    print("adding")
                    if "add" in self.data[m2m] and type(self.data[m2m]) == list:
                        getattr(qs[0], m2m).add(*self.data[m2m]['add'])
                    if "delete" in self.data[m2m] and type(self.data[m2m]) == list:
                        getattr(qs[0], m2m).remove(*self.data[m2m]['delete'])
        return self.other_response()
    
    def delete(self, request, *args, **kwargs):
        '''
        Delete an entity. This is a no payload endpoint where you can delete either in bulk 
        or singly.
        
        Filtering is done in the same way as GET.
        
        Will return status 204 if successful.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            if "ids" not in self.params:
                return err("Did not contain any valid ids to delete.")
        deletes = self._get_qs(*args, **kwargs)        
        deletes.delete_entity()
        return self.other_response()
    
    def set_headers(self, response, headers):
        '''
        Set a dictionary of headers to the HttpResponse object.
        
        @param response: the HttpResponse
        @param headers: the headers dictionary
        '''
        for key, val in headers.items:
            setattr(response, key, val)
    
    def response(self, qs, headers = {}):
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
        if 'xml' in self.accept:
            if not self.fields:
                data = sz.serialize("xml", qs)
            else:
                data = sz.serialize("xml", qs, fields = self.fields)
            ct = "application/xml"
        else: #defaults to json if nothing else is found of appropriate use
            data = serialize(self, qs)
            ct = "application/json"
        resp = HttpResponse(data, content_type = ct)
        if headers:
            self.set_headers(resp, headers)
        return resp
    
    def other_response(self, data = None, headers = {}):
        '''
        Returns a response according to the type of request made. This is done by passing in the 
        Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
        to json. Data should already be formatted in the correct Content-Type. This is a utility for sending all other responses.
        
        @param request: the request object
        @param data: the data to send; if None will send nothing with status 204
        @return the HttpResponse object
        '''
        if data is not None:
            if 'xml' in self.accept:
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
    
    class Meta:
        abstract = False     
        
class ModelAsView(ModelWrapper, BaseModelAsView):
    class Meta:
        abstract = True  

class UserModelAsView(ABUWrapper, BaseModelAsView):
    class Meta:
        abstract = True
'''
Created on May 17, 2015

@author: derigible
'''
from django.db import models as m
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.conf import settings

from mviews.modelviews import ModelAsView as mav


class PosterManager(BaseUserManager):
    def create_user(self, email, password=None):
        """
        Creates and saves a Poster with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email))

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, date_of_birth, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.level = 5
        user.save(using=self._db)
        return user
        
class Poster(AbstractBaseUser):
    '''
    The poster of an Entry. Each poster is signed in and unique in the system.
    '''
    email = m.EmailField('The email of the poster. This is also the username.', max_length = 254, unique=True)
    joined_on = m.DateTimeField('The time the poster first joined our blog.', auto_now_add = True)
    level = m.SmallIntegerField('The level of the user.', default = 0)
    
    public_fields = ("id", "email", "joined_on", "level", "comment_set", "label_set", "post_set", "last_login")
    
    objects = PosterManager()
    
    USERNAME_FIELD = 'email'
    
    levels = {
              0 : "watcher",
              1 : "commenter",
              2 : "moderator",
              3 : "creator",
              4 : "master",
              5 : "overlord"
              }
    
    def get_full_name(self):
        '''
       Mandatory Override of AbstractBaseUser.get_full_name(self)
       '''
        return self.email
    
    def get_short_name(self):
        '''
        Mandatory Override of AbstractBaseUser.get_short_name(self)
        '''
        return self.email.split('@')[0] #get just the username
    
    def set_password(self, raw_password, *args, **kwargs):
        '''
        Override of AbstractBaseUser.set_password(self, raw_password):
        
        This method will do some constraint validation on the password before saving it if settings.VALIDATE_PASSWORD_RULES is set to True
        '''
        if settings.VALIDATE_PASSWORD_RULES:
            if len(self.password) < 5:
                raise ValueError("The password needs to be over 4 characters long.")
        super(Poster, self).set_password(raw_password, *args, **kwargs)
    
    @classmethod    
    def get_level_name(self, level):
        return self.levels[level]
    
    @classmethod
    def get_level_by_name(self,level_name):
        for l, name in self.levels.items():
            if name == level_name:
                return l
        else:
            raise ValueError("The submitted level is not an allowed level number.")
    
    def __str__(self):
        return self.email

class Label(mav):
    '''
    Label of a comment or post. Only Posters of level 3 or above can create and update, level 1 and above to add, and level 4 and above to create/update/delete.
    '''
    name = m.TextField("The label name.", primary_key = True)
    created = m.DateTimeField('When the label was created.', auto_now_add = True)
    notes = m.TextField("Any notes about the label to help clarify what it is.", null=True)
    user = m.ForeignKey(Poster)
    
    register_route = True
    
    def save(self, *args, **kwargs):
        '''
        Save the label and ensure that the user has the appropriate level to create, update, and save.
        
        Raises a PermissionError if not allowed.
        '''
        if self.user.level < 3:
            raise PermissionError('Poster is not of level 3 or above. Cannot save or update.')
        super(Label, self).save(*args, **kwargs)
        
    def delete(self, *args, **kwargs):
        '''
        Ensure that the user has the appropriate level to delete object.
        
        Raises a PermissionError if not allowed.
        '''
        if self.user.level < Poster.get_level_by_name("master"):
            raise PermissionError('Poster is not of level "master" or above. Cannot save or update.')
        super(Label, self).save(*args, **kwargs)

class Entry(mav):
    created = m.DateTimeField('When the blogpost was created.', auto_now_add=True)
    last_updated = m.DateTimeField('When the blogpost was last modified.', auto_now=True)
    text = m.TextField('The text of the entry.')
    user = m.ForeignKey(Poster)
    
    register_route = True
    
    class Meta:
        abstract = True

class Post(Entry):
    '''
    Models a blog entry.
    '''
    title = m.TextField('The title of the blogpost.')
    labels = m.ManyToManyField(Label, related_name="posts")
    
    def save(self, *args, **kwargs):
        '''
        Save the post only after ensuring that the user making it the has the sufficient level. Raise an AuthenticationError
        if not.
        '''
        if self.user.level < Poster.get_level_by_name("creator"):
            raise PermissionError('Poster is not of level "creator" or above. Cannot save or update.')
        super(Post, self).save(*args, **kwargs)
    
    def __str__(self):
        return self.title
        
class Comment(Entry):
    '''
    Comments of a comment or a blog. Reference the comments of a comments by calling comments on the comment object.
    '''
    title = m.TextField('The title of the comment.', null=True)
    comment = m.ForeignKey('self', related_name = "comments", null=True)
    post = m.ForeignKey(Post, related_name = "comments")
    labels = m.ManyToManyField(Label, related_name="comments")
    
    def save(self, *args, **kwargs):
        '''
        Save the comment only after ensuring that the user making it the has the sufficient level. Raise an AuthenticationError
        if not.
        '''
        if self.user.level < Poster.get_level_by_name("commenter"):
            raise PermissionError('Poster is not of level "commenter" or above. Cannot save or update.')
        super(Comment, self).save(*args, **kwargs)
    
class Contact(mav):
    '''
    Contact me references. Attempts to tie them to a Poster once a user is created.
    '''
    email = m.EmailField('The email of the contact. This is also the username if is a poster.', max_length = 254, unique=True)
    phone = m.TextField('The phone number of the contact.', null = True)
    business = m.TextField('The business of the contact, if applicable.', null = True)
    notes = m.TextField('Any notes they wish to pass along.', null = True)
    contacted = m.DateTimeField("The datetime that the contact was created.", auto_now_add = True)
    user = m.ForeignKey(Poster, related_name = "contacts", null=True)
    
    register_route = True
    
    def save(self, *args, **kwargs):
        '''
        Checks to see if the contact is already a poster. If so, adds to ForeignKey.
        '''
        self.email = PosterManager.normalize_email(self.email)
        u = Poster.objects.filter(email = self.email)
        if len(u) > 0:
            self.user = u[0]
        super(Contact, self).save(*args, **kwargs)
        
    def __str(self):
        return self.email + " : " + self.notes
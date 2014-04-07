pad.mattdiesel.co.uk
====================

Google app engine snippet holder.

Writing this mostly to test the functionality of google app engine and get to know it. So far it's been a great success in that regard as there is a lot of code already using the datastore, memcache and other functions.

In order to run this locally, you must download pygments and put it in the lib directory. All the libraries come ready shipped with google app engine so nothing to do there.

A copy of this application is being run online at [pad.mattdiesel.co.uk](http://pad.mattdiesel.co.uk/), it may be several versions behind.


It is now also possible to add snippets by email. The email takes the subject line to be the title, and can also specify the language in brackets, so "Test Snippet [autoit]" will create a new snippet called "Test Snippet", with a slug of "test-snippet", using AutoIt as the language. The body of the email is used as the description, and the file name and content of the snippet are taken from the first attachment.

Emails must be sent to put@pad-matt-diesel.appspotmail.com, from an email address associated with a user already.
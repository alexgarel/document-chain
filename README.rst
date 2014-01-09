Document chain
================

This project aim at providing a simple asynchronous task handler
originally geared towards document transformations.

It focus mostly on ease of operating and deployement.

What it does
==============

It is intended as an independant service for a web application.

Currently it provides handlers to

- transform document to PDF (or other formats) using libreoffice
- callback an http service, to execute an action, or postback files
- generate PDF from RML

You can easily add more services as small Python programs.

The project also provides a secure wsgi service
in charge of feeding back user with the result of a transformation.

Overall, this helps keeping time / memory and CPU consuming tasks
out of a web application
and helps queuing tasks to avoid traffic jam.

How
====

The asynchronous task design is made to be easy to operate :

- Each task is represented by a *.ini* file giving parameters for each steps.
- Each queue is a simple folder.
- Each worker logs directly in the task file.

You can monit errors using a file monitoring tool like monit,
get on your server via ssh and just move your files around, read and edit them.

Workers are notified of new tasks thanks to inotify
so notification is immediate.

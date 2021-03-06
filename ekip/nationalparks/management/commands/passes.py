import csv

from django.core.management.base import BaseCommand
from nationalparks.models import FederalSite


def determine_site_type(name, website):
    """ The name (or website)  of a Federal Site in this list provides an
    indication of what type of site it might be. This extracts that out. """

    name_fragments = [
        (' BLM', 'BLM'), (' NF', 'NF'), ('National Forest', 'NF'),
        (' NWR', 'NWR'), (' NHS', 'NHS'), (' NRA', 'NRA'),
        ('National Recreation Area', 'NRA'),
        ('National Wildlife Refuge', 'NWR'), ('Fish and Wildlife', 'NWR')]

    for fragment, code in name_fragments:
        if fragment in name:
            return code

    website_fragments = [
        ('fs.fed.us', 'NF'), ('fs.usda.gov', 'NF'),
        ('blm.gov', 'BLM'), ('fws.gov', 'NWR'), ('nps.gov', 'NPS')]

    for fragment, code in website_fragments:
        if fragment in website:
            return code

    return 'OTH'


def phone_number(pstr):
    """ Extract the extension from the phone number if it exists. """

    if ';' in pstr:
        # In one case we have multiple phone numbers separated by a
        # semi-colon. We simply pick the first one. Note this means we're
        # "throwing away" the other phone numbers.
        pstr = pstr.split(';')[0]

    for m in [' x ', 'ext.', 'ext']:
        if m in pstr:
            phone, extension = pstr.split(m)
            return (phone.strip(), extension.strip())
    return (pstr.strip(), None)


def process_site(site, next_version):
    """ Create an entry in the database for a federal site."""

    # Some rows in the CSV don't represent sites. This is indicative by them
    # missing the city name.
    if site['city'] != '':
        phone, phone_extension = phone_number(site['phone'])
        annual = site['annual'].upper() == 'YES'
        senior = site['senior'].upper() == 'YES'
        access = site['access'].upper() == 'YES'
        site_type = determine_site_type(site['name'], site['website'])

        sites = FederalSite.objects.filter(name=site['name'], city=site['city'])

        if len(sites) > 0:
            # If we encounter a duplicate, let's update instead of inserting.
            fs = sites[0]
        else:
            fs = FederalSite()

        fs.name = site['name']
        fs.site_type = site_type
        fs.phone = phone
        fs.phone_extension = phone_extension
        fs.city = site['city']
        fs.state = site['state']
        fs.website = site['website']
        fs.annual_pass = annual
        fs.senior_pass = senior
        fs.access_pass = access
        fs.version = next_version
        fs.save()

def get_next_version():
    """ The FederalSite objects are versioned. Determine the last version by
    looking at an active site. """

    random_site = FederalSite.objects.filter(active_participant=True)[0]
    return random_site.version + 1


def deactivate_sites(next_version):
    """ Sites that have a lower version than the current version are marked as
    deactivated, as they are clearly not particpating in the passes program.
    """

    deactivated = FederalSite.objects.filter(version__lt=next_version)

    # Using update means save() doesn't get called. We want to update the
    # timestamp. 
    for fs in deactivated:
        fs.active_participant = False
        fs.save()
        
    
def read_pass_list(filename):
    next_version = get_next_version()

    with open(filename, 'r', encoding='latin-1') as passcsv:
        field_names = [
            'name', 'phone', 'city', 'state', 'website', 'annual', 'senior',
            'access']
        passreader = csv.DictReader(
            passcsv, fieldnames=field_names, delimiter=',') 

        for l in passreader:
            process_site(l, next_version)

    deactivate_sites(next_version)
        

class Command(BaseCommand):
    """ Read and import a pass list. """

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs=1)

    def handle(self, *args, **options):
        filename = options['filename'][0]
        read_pass_list(filename)

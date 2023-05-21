# Mobile Client

## The Thesis

Protecting Location Privacy in Reverse Geocoding applications

### abstract

The analysis of an individual's movement during their day-to-day life allows for inference of identifying information. An individual's use of location-based services (LBS) can allow the LBS provider to produce a record of the individual's trajectory, that could allow identification of otherwise anonymous LBS-users. A reverse geocoder is such an LBS, which matches a pair of coordinates in geographic space with a geographic feature that is found at the given location and returns information about that feature, usually as a street address. In this work, a location-privacy preserving mechanism (LPPM) for the application of reverse geocoding is presented. A prototype of it is evaluated in its resistance against user-identity inference, correctness, and performance by comparing it to an existing reverse geocoding solution in the simulation of an individual's usage throughout their daily life. Concluding, this work will demonstrate the LPPM's successful prevention of clustering-based inference attacks on an individual's identity, as well as some of its advantages and disadvantages in comparison to an existing solution, the Nominatim reverse geocoder.
## Mobile Client

The MC can be found within the mobileClient directory.
requirements appended in `requirements.txt`
Requires an MES (or a reverse proxy to one) already running.
On default, requests can be made through localhost:8081/reverse

released under the MIT license (license.txt)

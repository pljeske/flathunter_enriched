import json

from jsonpath_ng import parse

with open("result.json", "r") as file:
    json_file = json.loads(file.read())
    entries_path = parse("$..['resultlist.realEstate']")
    for entry in entries_path.find(json_file):
        images_path = parse("$..galleryAttachments.attachments[*].urls[0].url['@href']")
        rent_warm_path = parse("$.calculatedTotalRent.totalRent.value")
        print(f"Rent warm: {rent_warm_path.find(entry)}, Images: {images_path.find(entry)}")
        address = entry.value['address']
        contact_details = entry.value['contactDetails']
        paywall_listing = entry.value['paywallListing']['active']
        rent_cold = entry.value['price']['value']
        rooms = entry.value['numberOfRooms']
        living_space = entry.value['livingSpace']
        has_balcony = entry.value['balcony']
        rent_warm = entry.value['calculatedTotalRent']['totalRent']['value']
        image_urls = []
        for attachment in entry.value['galleryAttachments']['attachment']:
            full_url = attachment['urls'][0]['url']['@href']
            image_urls.append(full_url.split("/ORIG")[0])
            # image_urls.append(attachment['urls'][0]['url'].split("/ORIG")[0])

        print(f"{address}, {contact_details}, {paywall_listing}, {rent_cold}, {rooms}, {living_space}, {has_balcony}, {rent_warm}, {image_urls}")

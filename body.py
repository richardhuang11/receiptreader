import requests
import json
import base64
import re
from collections import defaultdict, OrderedDict

with open("/Users/Richard/Documents/key.txt") as f:
    key = json.load(f)

input_file = "receipt-1-1.png"
image_file = "receipt-1-1.png"
with open(input_file, 'rb') as image:
    contents = image.read()
encoded_string = base64.b64encode(contents).decode('UTF-8')
body = {
  "requests":[
    {
      "image":{
        "content": encoded_string
      },
      "features":[
        {
          "type":"TEXT_DETECTION"
        }
      ]
    }
  ]
}
json_body = json.dumps(body)
r = requests.post("https://vision.googleapis.com/v1/images:annotate?key="
                  +key, json_body)
#print(r.text)

responses = json.loads(r.text)['responses'][0]
text_annotations = responses['textAnnotations']

#gets item prices with regex
def get_item_prices(text_annotations):
  regx = r"\d{0,2}\.\d{2}"
  items = []
  for item_dict in text_annotations:
    description = item_dict['description']
    if re.search(regx, description) != None:
      items.append(item_dict)
  return items

prices = get_item_prices(text_annotations)[1:] #remove the header stuff
#print(prices)

#gets y coordinates of the lines containing the prices
def get_coordinates(prices_text_annotations):
  y_coordinates = []
  for item_dict in prices_text_annotations:
    coordinates = item_dict['boundingPoly']['vertices'][0]
    y_coordinates.append(coordinates['y'])
    for i in range(-2,2): #buffer
      y_coordinates.append(int(coordinates['y']) + i)

  return y_coordinates

y_coords = get_coordinates(prices)

#dictionary containing name and bounded poly of items we want
def get_item_names(text_annotations, y_coords):
  item_names = []
  for item_dict in text_annotations:
    coordinates = item_dict['boundingPoly']['vertices']
    for coordinate in coordinates:
      if coordinate['y'] in y_coords and item_dict not in item_names: 
        item_names.append(item_dict)
        #print(item_dict)
  return item_names

item_names = get_item_names(text_annotations, y_coords)

#words that indicate the beginning of junk portion we don't want
blacklist = [r"[Mm][Aa][Ss][Tt][Ee][Rr][Cc][Aa][Rr][Dd]", r"[Vv][Ii][Ss][Aa]",
            r"[Ss]?[Uu]?[Bb]?[Tt][Oo][Tt][Aa][Ll]", r"[Ss][Aa][Ll][Ee][Ss]?",
            r"[Tt][Aa][Xx]", r"[Ss][Tt][Aa][Tt][Ee]", r"[Ll][Oo][Cc][Aa][Ll]"]

#want to get the y coordinates of the items that are in blacklist
# def get_blacklist_y_coords(item_names):
#   y_coords = []
#   for item in item_names:
#     for entry in blacklist:
#       if re.search(entry, item['description']) != None:
#         coordinates = item['boundingPoly']['vertices'][0]
#         y_coords.append(coordinates['y'])
#   return y_coords

# blacklist_y_coords = get_blacklist_y_coords(item_names)

#only interested in the lowest y-coordinate. Represents that the item is higher
#up on the receipt
def get_lowest_blacklist_y_coord(item_names):
  y_coords = []
  for item in item_names:
    for entry in blacklist:
      if re.search(entry, item['description']) != None:
        coordinates = item['boundingPoly']['vertices'][0]
        y_coords.append(coordinates['y'])
  return min(y_coords)

min_blacklist_y_coord = get_lowest_blacklist_y_coord(item_names)

#filters everything at or below the min y coordinate. Not interested in anything below.
def filter_item_names(item_names, min_y_coord):
  to_delete = []
  for item in item_names:
    coordinates = item['boundingPoly']['vertices']
    for coordinate in coordinates:
      if coordinate['y'] >= min_y_coord: 
        to_delete.append(item)
  for item in to_delete:
    if item in item_names:
      item_names.remove(item)
  return item_names

item_names = filter_item_names(item_names, min_blacklist_y_coord)
# for item in item_names:
#   print(item)

#filters out entiries with duplicate names... buggy b/c deletes all duplicate prices,
# but some items have the same price
# unique_items = {}
# for item in item_names:
#   unique_items[item['description']] = item
# print(unique_items.keys())


def group_by_y(filtered_item_names):
  grouped_items = defaultdict(list)
  for item in filtered_item_names:
    coordinate = item['boundingPoly']['vertices']
    top_left = coordinate[0]['y']
    buffer_1 = int(top_left) - 1
    buffer_2 = int(top_left) - 2
    buffer_3 = int(top_left) + 1
    buffer_4 = int(top_left) + 2
    if buffer_1 in grouped_items.keys():
      grouped_items[buffer_1].append(item['description'])
    elif buffer_2 in grouped_items.keys():
      grouped_items[buffer_2].append(item['description'])
    elif buffer_3 in grouped_items.keys():
      grouped_items[buffer_3].append(item['description'])
    elif buffer_4 in grouped_items.keys():
      grouped_items[buffer_4].append(item['description'])
    else:
      grouped_items[top_left].append(item['description'])
  for item in grouped_items:
    grouped_items[item] = list(OrderedDict.fromkeys(grouped_items[item]))
  return grouped_items

grouped_items = group_by_y(item_names)

def grouped_items_to_items_and_prices(grouped_items):
  item_price = {}
  regx = r"\d{0,2}\.\d{2}"
  items = []
  prices = []
  for item in grouped_items: #iterate thru each key
    count = 0
    temp = ""
    for elem in grouped_items[item]: #iterate thru each element in list 
      if re.search(regx, elem) != None:
        prices.append(elem) 
      else:
        temp = temp + " " + elem
    items.append(temp[1:]) 
  for i in range(len(items)):
    item_price[items[i]] = prices[i]
  return item_price

item_price = grouped_items_to_items_and_prices(grouped_items)

def get_person_price():
  person_item = defaultdict(list)
  quit_words = ["yes", "Yes", "y", "Y", "YES"]
  quit = "no"
  while True:
    name = input("What is your name? ")
    person_quit = "no"
    while True:
      item = input("What is an item you bought? ")
      person_item[name].append(item)
      person_quit = input("Done? ")
      if person_quit in quit_words:
        break
    quit = input("Exit? ")
    if quit in quit_words:
      break
  return person_item

person_item = get_person_price()

def get_total_counts(person_item, item_price):
  item_counts = defaultdict(int)
  for item in item_price:
    item_counts[item] = 0
  for item in item_price:
    for person in person_item:
      if item in person_item[person]:
        item_counts[item] += 1
  return item_counts

total_counts = get_total_counts(person_item, item_price)

def payouts(person_item, total_counts, item_price):
  person_payouts = defaultdict(int)
  for person in person_item:
    for item in person_item[person]: #for each item the person bought
      person_payouts[person] += round(float(item_price[item])*1.0925/total_counts[item],2)
  return person_payouts

payouts = payouts(person_item, total_counts, item_price)

for payout in payouts:
  print(payout, payouts[payout])





import requests
from bs4 import BeautifulSoup
import boto3
import json
from decimal import Decimal
from datetime import date, timedelta

import sys

def extractSetNumberFromTitle(title):
    return [int(i) for i in title.split() if i.isdigit()]

def getInformation(url, headers=None):
    page = requests.get(url, headers=headers)
    soup = BeautifulSoup(page.content, 'html.parser')
    title = soup.find(id="section_title").get_text()
    title = title[:53].strip()
    code = extractSetNumberFromTitle(title)
    code = code[0]
    priceWhole = soup.find("span", class_="whole").get_text()
    priceRest = soup.find("span", class_="cents").get_text()
    price = priceWhole + "." + priceRest
    price = json.loads(json.dumps(price), parse_float=Decimal)
    return code, title, price

def checkIfItemInDynamoDB():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('lego-stats')
    response = table.get_item(
        Key = {
            'Date': str(date.today())
        }
    )
    if 'Item' in response:
        return True
    else:
        return False

def saveToDynamoDB(code, title, price):
    print("Saving data...")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('lego-stats')
    table.put_item(
        Item={
            'Date': str(date.today()),
            'Code': code, #int
            'Title': title,  # string
            'Price': price # number
        }
    )

def updateExistingField(price):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('lego-stats')
    response = table.get_item(
        Key={
            'Date': str(date.today())
        }
    )
    item = response['Item']
    item['Price'] = price
    table.put_item(Item=item)

def publish_text_message(phone_number, message):
    sns = boto3.resource("sns")
    sns.meta.client.publish(
        PhoneNumber=phone_number, Message=message)

def yesterdayPrice():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('lego-stats')
    yesterdayDate = date.today() - timedelta(days=1)
    response = table.get_item(
        Key={
            'Date': str(yesterdayDate)
        }
    )
    item = response['Item']
    return item['Price']

if __name__ == "__main__":
    if sys.argv[1] is None:
        url = 'https://www.mediaexpert.pl/zabawki/lego/lego/lego-ideas-miedzynarodowa-stacja-kosmiczna-21321'
    else:
        url = sys.argv[1]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
    }
    code, title, price = getInformation(url, headers)

    if checkIfItemInDynamoDB():
        updateExistingField(price)
    else:
        saveToDynamoDB(code, title, price)

    priceOnYesterday = yesterdayPrice()
    print(priceOnYesterday)
    if float(price) <= priceOnYesterday * Decimal(0.85):
        messageText = "Zestaw lego {} jest dzis tanszy o {} zl.".format(title, priceOnYesterday-Decimal(price))
        publish_text_message("+123456789", messageText)


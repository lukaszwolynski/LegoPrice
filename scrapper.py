import requests
from bs4 import BeautifulSoup
import boto3
import json
import os
from decimal import Decimal
from datetime import date, timedelta

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('lego-stats')

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
    table.put_item(
        Item={
            'Date': str(date.today()),
            'Code': code, #int
            'Title': title,  # string
            'Price': price # number
        }
    )

def updateExistingField(price):
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

    yesterdayDate = date.today() - timedelta(days=1)
    response = table.get_item(
        Key={
            'Date': str(yesterdayDate)
        }
    )
    item = response['Item']
    return item['Price']

def lambda_handler(event, context):
    url = os.getenv("URL")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
    }
    code, title, price = getInformation(url, headers)

    if checkIfItemInDynamoDB():
        updateExistingField(price)
    else:
        saveToDynamoDB(code, title, price)

    priceOnYesterday = yesterdayPrice()

    if Decimal(price) <= Decimal(priceOnYesterday) * Decimal(0.90):
        messageText = "Zestaw lego {} jest dzis tanszy o {} zl.".format(title, Decimal(priceOnYesterday)-Decimal(price))
        publish_text_message("+48123456789", messageText)

    return {
        'statusCode': 200,
        'body': "Successful writing"
    }
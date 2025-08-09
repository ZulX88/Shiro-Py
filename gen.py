from neonize.client import NewClient

client = NewClient("db.sqlite3")

number = input("Nomor WA : ")
client.PairPhone(str(number), show_push_notification=True)

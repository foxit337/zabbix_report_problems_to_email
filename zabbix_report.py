from pyzabbix import ZabbixAPI
from prettytable import PrettyTable
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from configparser import ConfigParser
from datetime import datetime, timedelta


def send_email(subject, body, recipients):
    from_addr = config['gmail']['user']
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(config['gmail']['user'], config['gmail']['password'])

    server.sendmail(from_addr, recipients, msg.as_string())
    server.quit()

def main(send_email_flag):
    zapi = ZabbixAPI(config['zabbix']['url'])
    zapi.login(config['zabbix']['user'], config['zabbix']['password'])

    active_hosts = zapi.host.get(output=['hostid'], filter={'status': '0'})
    year_ago_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')

    # Create two separate tables for free disk space problems and other problems
    free_disk_table = PrettyTable()
    free_disk_table.field_names = ["Host", "Problem", "Severity"]

    other_problems_table = PrettyTable()
    other_problems_table.field_names = ["Host", "Problem", "Severity"]

    problems = zapi.problem.get(selectAcknowledges="extend", selectTags="extend", output="extend", filter={'severity': ['4', '5'], 'suppressed': '0','age': year_ago_date})

    for problem in problems:
        try:
            trigger = zapi.trigger.get(triggerids=problem['objectid'], selectHosts='extend')

            if trigger and trigger[0]['hosts']:
                host_id = trigger[0]['hosts'][0]['hostid']
                if any(host['hostid'] == host_id for host in active_hosts):
                    severity = problem['severity']

                    if 'description' in trigger[0]:
                        if trigger[0]['status'] == '0':
                            if problem['name'].startswith("Free disk space"):
                                    free_disk_table.add_row([trigger[0]['hosts'][0]['host'],
                                                   problem['name'],
                                                   severity])
                            else:
                                 other_problems_table.add_row([trigger[0]['hosts'][0]['host'],
                                                   problem['name'],
                                                   severity])
        except Exception as e:
            print(f"Error processing problem: {e}")

    # Print the table for free disk space problems first and then the other problems table
    print("Free Disk Space Problems:")
    print(free_disk_table)
    print("Other Problems:")
    print(other_problems_table)

    if send_email_flag:
        recipients = config['recipients']['to'].split(', ')
        total_problems = len(free_disk_table.rows) + len(other_problems_table.rows)
        email_subject = 'Zabbix Problems Report'
        email_body = f'<html><body><h1>Total problems: {total_problems}</h1><h2>Free Disk Space Problems:</h2>{free_disk_table.get_html_string()}<h2>Other Problems:</h2>{other_problems_table.get_html_string()}</body></html>'

        send_email(email_subject, email_body, recipients)

    zapi.user.logout()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Retrieve and display Zabbix problems.')
    parser.add_argument('--send-email', action='store_true', help='Send the report via email')
    args = parser.parse_args()

    config = ConfigParser()
    config.read('/usr/local/bin/zabbix_config.ini')

    main(args.send_email)

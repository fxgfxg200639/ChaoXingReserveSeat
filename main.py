import json
import time
import argparse
import os
import logging
import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


from utils import reserve, get_user_credentials

SLEEPTIME = 0.5  # 每次抢座的间隔
MAX_ATTEMPT = 20  # 最多尝试20次
RESERVE_NEXT_DAY = True
ENABLE_SLIDER = True


def login_and_reserve(users, usernames, passwords, action, success_list=None):
    logging.info(
        f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nMAX_ATTEMPT: {MAX_ATTEMPT}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )
    if action and len(usernames.split(",")) != len(users):
        raise Exception("user number should match the number of config")
    if success_list is None:
        success_list = [False] * len(users)
    current_dayofweek = datetime.datetime.now().strftime("%A")
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        if action:
            username, password = (
                usernames.split(",")[index],
                passwords.split(",")[index],
            )
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue
        if not success_list[index]:
            logging.info(
                f"----------- {username} -- {times} -- {seatid} try -----------"
            )
            s = reserve(
                sleep_time=SLEEPTIME,
                max_attempt=MAX_ATTEMPT,
                enable_slider=ENABLE_SLIDER,
                reserve_next_day=RESERVE_NEXT_DAY,
            )
            s.get_login_status()
            s.login(username, password)
            s.requests.headers.update({"Host": "office.chaoxing.com"})
            suc = s.submit(times, roomid, seatid, action)
            success_list[index] = suc
    return success_list


def main(users, action=False):
    # GitHub服务器是UTC时区，北京时间22:00 = UTC14:00
    now = datetime.datetime.now()
    logging.info(f"服务器当前UTC时间: {now}")
    target = now.replace(hour=14, minute=0, second=0, microsecond=0)
    if now < target:
        wait_sec = (target - now).total_seconds()
        logging.info(f"距离北京时间22:00（UTC14:00）还有{int(wait_sec)}秒，等待准点...")
        time.sleep(wait_sec)
    
    logging.info(f"开始抢座，当前UTC时间: {datetime.datetime.now()}")
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
    success_list = None
    current_dayofweek = datetime.datetime.now().strftime("%A")
    today_reservation_num = sum(
        1 for d in users if current_dayofweek in d.get("daysofweek")
    )
    
    success_list = login_and_reserve(
        users, usernames, passwords, action, success_list
    )
    if sum(success_list) == today_reservation_num:
        logging.info(f"全部预约成功！")
    else:
        logging.info(f"已完成{MAX_ATTEMPT}次尝试，结束")


def debug(users, action=False):
    logging.info(f"Debug Mode start!")
    if action:
        usernames, passwords = get_user_credentials(action)
    current_dayofweek = datetime.datetime.now().strftime("%A")
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        if type(seatid) == str:
            seatid = [seatid]
        if action:
            username, password = (
                usernames.split(",")[index],
                passwords.split(",")[index],
            )
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue
        logging.info(f"----------- {username} -- {times} -- {seatid} try -----------")
        s = reserve(
            sleep_time=0.5,
            max_attempt=20,
            enable_slider=True,
            reserve_next_day=True,
        )
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({"Host": "office.chaoxing.com"})
        suc = s.submit(times, roomid, seatid, action)
        if suc:
            return


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    parser = argparse.ArgumentParser(prog="Chao Xing seat auto reserve")
    parser.add_argument("-u", "--user", default=config_path, help="user config file")
    parser.add_argument(
        "-m",
        "--method",
        default="reserve",
        choices=["reserve", "debug", "room"],
        help="for debug",
    )
    parser.add_argument(
        "-a",
        "--action",
        action="store_true",
        help="use --action to enable in github action",
    )
    args = parser.parse_args()
    func_dict = {"reserve": main, "debug": debug}
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)
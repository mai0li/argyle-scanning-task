import json
import uuid
import traceback
import credentials
from datetime import datetime
from pathlib import Path
from serialize import User, Address
from playwright.sync_api import Playwright, sync_playwright


def run(playwright: Playwright) -> None:
    """
    Main crawler operating loop.
    Starts playwright. Fires chromium up. Calls functions. Does stuff. Outputs stuff.

    :param playwright: "A playwright is a person who writes plays for the stage. - Wikipedia"
    :return: 0
    """

    # put some goggles and a fake mustache
    configs = ["--disable-blink-features=AutomationControlled", "--disable-gpu", "--no-sandbox", "--enable-javascript",
               "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu "
               "Chromium/97.0.4649.106 Chrome/97.0.4649.106 Safari/537.36"]
    browser = playwright.chromium.launch(headless=False, args=configs)
    context = browser.new_context()
    page = context.new_page()

    # Did you log in?
    if login(page):
        # Good. Wait until job feed gets rendered, and screenshot page as a test.
        page.wait_for_selector('[data-test="feed-best-match"]')
        page.screenshot(
            path=f'./output/{credentials.USERNAME}/screenshots/{datetime.now().strftime("%Y-%m-%d-%H_%M_%S")}_successful_login.png',
            full_page=True)

        # Now, scrap some data.
        level1_info = collect_home_info(page)

        # Save it to a json file.
        with open(f'./output/{credentials.USERNAME}/level1.json', 'w', encoding='utf-8') as f:
            json.dump(level1_info, f, ensure_ascii=False, indent=4)

        # Now, scrap additional data.
        level2_info = collect_profile_settings_info(page)

        # Save additional data to a json file.
        with open(f'./output/{credentials.USERNAME}/level2.json', 'w', encoding='utf-8') as f:
            json.dump(level2_info, f, ensure_ascii=False, indent=4)

    else:
        # Oh no, you did not log in! Save screenshot as documentation.
        page.screenshot(
            path=f'./output/{credentials.USERNAME}/screenshots/{datetime.now().strftime("%Y-%m-%d-%H_%M_%S")}_unsuccessful_login.png',
            full_page=True)
        print('Login was unsuccessful. Check screenshots folder for additional info.')

    # ---------------------
    # we out here
    context.close()
    browser.close()


def login(page):
    """
    Logs in.
    Current implementation assumes 30 seconds if manual interaction needed (typing OTP from Google Authenticator).

    :param page: current page, forged at run(playwright)
    :return: returns False for error, True for success
    """
    try:
        page.goto("https://www.upwork.com/ab/account-security/login")
        page.click("[placeholder=\"Username or Email\"]")
        page.fill("[placeholder=\"Username or Email\"]", credentials.USERNAME)
        page.click("text=Continue with Email")
        page.wait_for_selector('#login_password')
        page.fill("#login_password", credentials.PASSWORD)
        page.wait_for_selector('.side-by-side > div > .up-form-group > .mb-0 > .up-checkbox-label')
        page.click('.side-by-side > div > .up-form-group > .mb-0 > .up-checkbox-label')
        page.wait_for_selector('#login_control_continue')
        page.click('#login_control_continue')

        # Saves time if password is incorrect
        try:
            page.locator("text=Oops! Password is incorrect").wait_for(state='visible', timeout=3000)
            return False
        except:

            # Saves time if recaptcha pops up
            try:
                page.locator("text=Please fix the errors below").wait_for(state='visible', timeout=3000)
                return False
            except:

                # Back to correct credentials routine
                # This is the possibly needed manual interaction part we were talking about.
                # Excepts if OTP dialog pops and user does not submit OTP in 30s (or server fails to process login).
                page.wait_for_url('https://www.upwork.com/nx/find-work/best-matches')
                print('Info: Successful login attempt.')
                return True
    except:
        # Returns false if user did not submit OTP in 30s or unidentified error pops up
        return False


def collect_home_info(page):
    """
    Level 1.
    Collects "information you think is valuable".

    :param page: current page, forged at run(playwright) and processed through login(page).
    :return: Dictionary object containing collected info.
    """

    try:
        """
        I will build a dictionary containing all user fields, 
        but I need to initialize and populate fields holding multiple values first.
        These are: user job categories (array) and best job matches (dict).
        """

        categories = []
        for el in page.query_selector_all('.d-block.pb-10'):
            categories.append(el.inner_text())

        jobs_cards = page.locator('[data-test="job-tile-list"] > *')
        jobs = []
        for job_card in jobs_cards.all_inner_texts():
            job = job_card.split('\n')
            job_important_info = dict(job_title=job[0],
                                      job_type=job[3],
                                      job_description=job[
                                          5] if 'Only freelancers located in the United States may apply.' in job[
                                          4] else job[4],
                                      job_skills=job[7:-8] if 'more' == job[6] else job[6:-8] if 'more' == job[
                                          5] else job[5:-8],
                                      job_proposals=job[-8],
                                      job_verified=job[-6],
                                      job_rating=job[-4],
                                      job_client_spendings=job[-3][1:-1],
                                      job_country=job[-1])
            jobs.append(job_important_info)

        # All set for multiple value fields, just grab selectors for single-value ones and build the dict
        user_dict = dict(
            upwork_hash=page.get_attribute(selector='#fwh-sidebar-profile > a', name='href').split('~')[-1],
            avatar_url=page.get_attribute('#fwh-sidebar-profile > a > img', name='src'),
            name=page.inner_text('.profile-title'), title=page.inner_text('#fwh-sidebar-profile > div > p'),
            connections=int(page.inner_text('[data-test=sidebar-available-connects]').split(' ')[0]),
            week_availability=page.inner_text('[data-test=freelancer-sidebar-availability]').split('\n')[-1],
            profile_visibility=page.inner_text('[data-test=freelancer-sidebar-visibility]').split('\n')[-1],
            categories=categories,
            best_job_matches=jobs)

        # Return a delicious dict, ready to be saved as json via json.dumps() :)
        return user_dict

    except:
        # Prints stack trace if things get ugly
        traceback.print_exc()


def collect_profile_settings_info(page):
    """
    Level 2. Collects additional info.
    Makes it look like a JSON displayed at https://argyle.com/docs/developer-tools/api-reference#null-values.
    Outputs it as level2.json.
    Makes data serializable to an object.

    :param page: current page, forged at run(playwright) and processed through login(page) and collect_home_info(page).
    :return: Dictionary object containing collected info.
    """

    # Generated fields
    user_id = str(uuid.uuid4())
    user_account = str(uuid.uuid4())
    metadata = f'User crawled at {datetime.now().strftime("%Y-%m-%d-%H_%M_%S")}'

    # Already-in-homepage fields
    user_picture_url = page.get_attribute('#fwh-sidebar-profile > a > img', name='src')

    # Employer field (obtainable through visiting profile page)
    page.goto(f"https://www.upwork.com{page.get_attribute(selector='#fwh-sidebar-profile > a', name='href')}")
    user_employer = page.inner_text('h4.my-0').split('|')[1][1:]

    # Contact Info/Location fields (obtainable through visiting https://www.upwork.com/freelancers/settings/contactInfo)

    # Navigating through upper right menu might decrease chance of OTP dialog popping up
    page.wait_for_selector('.nav-right > .nav-d-none > .nav-item > .nav-item-label > .nav-avatar')
    page.click('.nav-right > .nav-d-none > .nav-item > .nav-item-label > .nav-avatar')
    page.wait_for_selector('.nav-d-none > .nav-dropdown-menu > .nav-options-desktop > ul > li:nth-child(1) > '
                           '.nav-menu-item > .up-s-nav-icon > svg')
    page.click('.nav-d-none > .nav-dropdown-menu > .nav-options-desktop > ul > li:nth-child(1) > .nav-menu-item > '
               '.up-s-nav-icon > svg')

    # Another circumstance where we need manual interaction.
    # Errors if OTP dialog pops up anyway, and user does not submit code in 30 seconds.
    # (Should I try bypassing this? Might be doable!)
    page.wait_for_url('https://www.upwork.com/freelancers/settings/contactInfo')

    # Clicks edit fields
    page.wait_for_selector('.up-card:nth-child(2) > .up-card-header > .up-btn > .up-icon > svg')
    page.click('.up-card:nth-child(2) > .up-card-header > .up-btn > .up-icon > svg')

    # Grab values from input fields
    first_name_handle = page.query_selector('//input[starts-with(@aria-label, "First name")]')
    first_name = first_name_handle.input_value()
    last_name_handle = page.query_selector('//input[starts-with(@aria-label, "Last name")]')
    last_name = last_name_handle.input_value()
    email_handle = page.query_selector('//input[starts-with(@aria-label, "Email")]')
    email = email_handle.input_value()

    # Address fields
    user_address_line_1 = page.inner_text('[data-test="addressStreet"]').split('\n')[0]
    user_address_line_2 = page.inner_text('[data-test="addressStreet2"]').split('\n')[0]
    user_address_city = page.inner_text('[data-test="addressCity"]')
    user_address_state = page.inner_text('[data-test="addressState"]').split(' ')[-1]
    user_address_zipcode = page.inner_text('[data-test="addressZip"]')
    user_address_country = page.inner_text('[data-test="addressCountry"]')

    level2_address_dict = dict(
        line1=user_address_line_1, line2=user_address_line_2, city=user_address_city,
        state=user_address_state, postal_code=user_address_zipcode, country=user_address_country
    )

    # Phone field
    user_phone_number = page.inner_text('[data-test="phone"]')

    # Builds level 2 dictionary, ready to be saved to a json via json.dumps()
    level2_dict = dict(
        id=user_id,
        account=user_account,
        employer=user_employer,
        created_at=None,
        updated_at=None,
        first_name=first_name,
        last_name=last_name,
        full_name=first_name+' '+last_name,
        email=email,
        phone_number=user_phone_number,
        birth_date=None,
        picture_url=user_picture_url,
        address=level2_address_dict,
        ssn=None,
        marital_status=None,
        gender=None,
        metadata=metadata

    )

    # Also, make data serializable to an object
    level2_serializable_object = User(id=user_id, account=user_account, employer=user_employer,
                                      created_at=None, updated_at=None,
                                      first_name=first_name, last_name=last_name, full_name=first_name+' '+last_name,
                                      email=email, phone_number=user_phone_number, birth_date=None,
                                      picture_url=user_picture_url,
                                      address=Address(line1=user_address_line_1, line2=user_address_line_2,
                                                      city=user_address_city, state=user_address_state,
                                                      postal_code=user_address_zipcode, country=user_address_country),
                                      ssn=None, marital_status=None, gender=None, metadata=metadata)

    # Testing serialization
    print('Crawled fields:')
    print('id:',level2_serializable_object.id)
    print('account:',level2_serializable_object.account)
    print('employer:',level2_serializable_object.employer)
    print('created_at:',level2_serializable_object.created_at)
    print('updated_at:',level2_serializable_object.updated_at)
    print('first_name:',level2_serializable_object.first_name)
    print('last_name:',level2_serializable_object.last_name)
    print('full_name:',level2_serializable_object.full_name)
    print('email:',level2_serializable_object.email)
    print('phone_number:',level2_serializable_object.phone_number)
    print('birth_date:',level2_serializable_object.birth_date)
    print('picture_url:',level2_serializable_object.picture_url)
    print('address_line1:',level2_serializable_object.address.line1)
    print('address_line2:',level2_serializable_object.address.line2)
    print('address_city:',level2_serializable_object.address.city)
    print('address_state:',level2_serializable_object.address.state)
    print('address_postal_code:',level2_serializable_object.address.postal_code)
    print('address_country:',level2_serializable_object.address.country)
    print('ssn:',level2_serializable_object.ssn)
    print('marital_status:',level2_serializable_object.marital_status)
    print('gender:',level2_serializable_object.gender)
    print('metadata:',level2_serializable_object.metadata)

    # Returns a delicious dict, ready to be saved to json via json.dumps()
    return level2_dict


if __name__ == '__main__':
    # create crawler folders named after soon-to-be crawled user.
    Path(f'./output/{credentials.USERNAME}/').mkdir(parents=True, exist_ok=True)
    Path(f'./output/{credentials.USERNAME}/screenshots/').mkdir(parents=True, exist_ok=True)

    # go web, go!
    with sync_playwright() as playwright:
        run(playwright)

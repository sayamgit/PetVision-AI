const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE||undefined,headless:true});
 const finder=await browser.newContext({geolocation:{latitude:12.9716,longitude:77.5946},permissions:['geolocation']});
 await finder.addInitScript(()=>{
   const native=navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
   window.geoCalls=0;window.geoMode='native';
   navigator.geolocation.getCurrentPosition=(yes,no,options)=>{
     window.geoCalls++;
     if(window.geoMode==='pending'){window.geoRelease=()=>yes({coords:{latitude:12.9716,longitude:77.5946}});return;}
     if(window.geoMode.startsWith('error')){setTimeout(()=>no({code:Number(window.geoMode.slice(-1))}),30);return;}
     native(yes,no,options);
   };
 });
 const page=await finder.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(fixture.public);
 assert.equal(await page.evaluate(()=>window.geoCalls),0,'QR page must not request location automatically');
 await page.getByRole('button',{name:'Use my current location'}).click();
 await page.waitForFunction(()=>document.getElementById('id_latitude').value==='12.971600');
 assert.equal(await page.locator('#id_longitude').inputValue(),'77.594600');
 assert.equal(await page.locator('#id_share_location').isChecked(),false);
 await page.locator('#id_message').fill('QR consent verification');
 await page.getByRole('button',{name:'Send report to owner'}).click();
 await page.getByText('Confirm location sharing or clear the coordinates.',{exact:true}).waitFor();
 await page.locator('#id_share_location').check();
 await page.getByRole('button',{name:'Send report to owner'}).click();await page.waitForURL(/received/);
 const owner=await browser.newContext();const ownerPage=await owner.newPage();
 await ownerPage.goto(fixture.base+'/accounts/login/');await ownerPage.locator('#id_username').fill('qrcheckowner');await ownerPage.locator('#id_password').fill('QA-Only-Temporary-742!');
 await ownerPage.locator('form button.full').click();await ownerPage.waitForURL(fixture.base+'/');
 await ownerPage.goto(fixture.base+`/pets/${fixture.pet}/`);
 assert(await ownerPage.getByText('QR consent verification',{exact:true}).isVisible());
 assert.match(await ownerPage.locator('.reports').textContent(),/12\.971600, 77\.594600/);
 const qr=await owner.request.get(fixture.base+`/pets/${fixture.pet}/qr.png`);
 assert(qr.ok());assert.equal(qr.headers()['content-type'],'image/png');
 const png=await qr.body();assert.equal(png.subarray(1,4).toString(),'PNG');
 if(process.env.QR_CHECK_SCREENSHOT) await ownerPage.screenshot({path:process.env.QR_CHECK_SCREENSHOT,fullPage:true});
 await page.goto(fixture.public);assert.equal(await page.getByText('QR consent verification',{exact:true}).count(),0,'Owner inbox must stay private');
 await page.getByRole('button',{name:'Use my current location'}).click();await page.waitForFunction(()=>document.getElementById('id_latitude').value!=='');await page.locator('#id_share_location').check();
 await page.evaluate(()=>{window.geoMode='error1';});await page.getByRole('button',{name:'Use my current location'}).click();
 await page.getByText(/Location permission was denied/).waitFor();
 assert.equal(await page.locator('#id_latitude').inputValue(),'');assert.equal(await page.locator('#id_share_location').isChecked(),false);
 await page.locator('#id_message').fill('QR denied verification');await page.locator('#id_location_text').fill('Near the library');
 await page.getByRole('button',{name:'Send report to owner'}).click();await page.waitForURL(/received/);
 for(const [mode,message] of [['error2','could not determine'],['error3','timed out']]){
   await page.goto(fixture.public);await page.evaluate(m=>{window.geoMode=m;},mode);
   await page.getByRole('button',{name:'Use my current location'}).click();await page.getByText(new RegExp(message)).waitFor();
   assert.equal(await page.locator('#id_latitude').inputValue(),'');assert.equal(await page.locator('#share-location').isDisabled(),false);
 }
 await page.goto(fixture.public);await page.evaluate(()=>{window.geoMode='pending';});
 await page.locator('#id_message').fill('Must not be submitted while waiting');await page.getByRole('button',{name:'Use my current location'}).click();
 await page.getByRole('button',{name:'Send report to owner'}).click();await page.getByText(/Please wait for the location result/).waitFor();assert.equal(page.url(),fixture.public);
 await page.getByRole('button',{name:'Clear location',exact:true}).click();await page.evaluate(()=>window.geoRelease());
 assert.equal(await page.locator('#id_latitude').inputValue(),'');assert.equal(await page.locator('#share-location').isDisabled(),false);
 await page.goto(fixture.public);await page.evaluate(()=>{Object.defineProperty(navigator,'geolocation',{value:undefined,configurable:true});});
 await page.getByRole('button',{name:'Use my current location'}).click();await page.getByText(/Location is unavailable in this browser/).waitFor();
 await page.goto(fixture.public);await page.evaluate(()=>{Object.defineProperty(window,'isSecureContext',{value:false,configurable:true});});
 await page.getByRole('button',{name:'Use my current location'}).click();await page.getByText(/needs a secure HTTPS page/).waitFor();assert.equal(await page.evaluate(()=>window.geoCalls),0);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({passed:['QR page does not request GPS on load','allowed location captured','explicit sharing consent required','report visible in owner inbox','public visitors cannot read reports','QR PNG generated','failed retry clears old consented location','denied permission still permits landmark-only report','unavailable and timeout messages','pending submission blocked','clear cancels late callbacks','unsupported browser and insecure context explained'],browserErrors:errors},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

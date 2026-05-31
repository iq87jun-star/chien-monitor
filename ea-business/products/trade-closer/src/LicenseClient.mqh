//+------------------------------------------------------------------+
//|                                                LicenseClient.mqh  |
//|                            RiskGuard — license verification layer |
//+------------------------------------------------------------------+
//
//  Two build modes (selected via a compile-time macro in RiskGuard.mq5):
//
//   * RG_BUILD_MARKET   -> MQL5 Market build.
//                          The platform handles licensing (account / PC
//                          binding, activations). This module compiles to a
//                          no-op that always returns true. DO NOT call
//                          WebRequest or any external resource in this build:
//                          MQL5 Market forbids third-party DLLs and external
//                          license calls.
//
//   * RG_BUILD_SELF     -> Self-hosted build (own LP / Gumroad sale).
//                          Verifies a perpetual (buy-once) license key against
//                          your own HTTPS license API via WebRequest (no DLL).
//                          The account login is bound server-side.
//
//  SECURITY: no secrets are hardcoded here. The license server holds the
//  signing secret and validates the key + account. The client only sends the
//  key and account login and trusts the HTTPS response.
//
//  NOTE: WebRequest() requires the API host to be added in MetaTrader:
//        Tools > Options > Expert Advisors > "Allow WebRequest for listed URL".
//        This is documented in manual/setup-*.md.
//+------------------------------------------------------------------+
#property strict

//--- result of a license check
struct RGLicenseResult
  {
   bool   ok;        // license valid for this account
   string message;   // human-readable reason (for the chart comment / log)
  };

//+------------------------------------------------------------------+
//| Tiny helper: extract a string value from a flat JSON response.   |
//| Avoids pulling a full JSON parser into a single-purpose tool.    |
//| Looks for  "key":"value"  or  "key":value  (bool/number).        |
//+------------------------------------------------------------------+
string RGJsonValue(const string json,const string key)
  {
   string needle="\""+key+"\"";
   int p=StringFind(json,needle);
   if(p<0) return("");
   p=StringFind(json,":",p);
   if(p<0) return("");
   p++;
   // skip spaces
   while(p<StringLen(json) && (StringGetCharacter(json,p)==' ')) p++;
   bool quoted=(p<StringLen(json) && StringGetCharacter(json,p)=='\"');
   if(quoted) p++;
   string val="";
   for(int i=p;i<StringLen(json);i++)
     {
      ushort c=StringGetCharacter(json,i);
      if(quoted && c=='\"') break;
      if(!quoted && (c==',' || c=='}' || c==' ')) break;
      val+=ShortToString(c);
     }
   return(val);
  }

//+------------------------------------------------------------------+
//| Verify the license.                                              |
//|  product   : product identifier (e.g. "risk-guard")             |
//|  key       : buyer's perpetual license key                      |
//|  serverUrl : your HTTPS license endpoint (self build only)      |
//+------------------------------------------------------------------+
RGLicenseResult RGCheckLicense(const string product,const string key,const string serverUrl)
  {
   RGLicenseResult r;
   r.ok=false;
   r.message="";

#ifdef RG_BUILD_MARKET
   //--- MQL5 Market handles licensing; never call out to a server here.
   r.ok=true;
   r.message="Market licensed";
   return(r);
#else
   if(StringLen(key)==0)
     {
      r.message="License key is empty. Enter your key in the inputs.";
      return(r);
     }
   if(StringLen(serverUrl)==0)
     {
      r.message="License server URL is not configured.";
      return(r);
     }

   long   login   = AccountInfoInteger(ACCOUNT_LOGIN);
   string company = AccountInfoString(ACCOUNT_COMPANY);

   string body=StringFormat(
                "{\"product\":\"%s\",\"key\":\"%s\",\"account\":\"%I64d\",\"broker\":\"%s\"}",
                product,key,login,company);

   char   post[];
   char   result[];
   string headers="Content-Type: application/json\r\n";
   string resultHeaders;
   int    timeout=5000;

   StringToCharArray(body,post,0,StringLen(body),CP_UTF8);
   ResetLastError();
   int code=WebRequest("POST",serverUrl,headers,timeout,post,result,resultHeaders);

   if(code==-1)
     {
      int err=GetLastError();
      if(err==4014) // ERR_FUNCTION_NOT_ALLOWED
         r.message="WebRequest blocked. Add the license host in Tools>Options>Expert Advisors.";
      else
         r.message=StringFormat("License server unreachable (err %d).",err);
      return(r);
     }

   string resp=CharArrayToString(result,0,WHOLE_ARRAY,CP_UTF8);

   if(code!=200)
     {
      r.message=StringFormat("License rejected (HTTP %d).",code);
      return(r);
     }

   string valid=RGJsonValue(resp,"valid");
   if(valid=="true")
     {
      r.ok=true;
      r.message="Licensed";
     }
   else
     {
      string reason=RGJsonValue(resp,"reason");
      r.message=(StringLen(reason)>0)?reason:"License not valid for this account.";
     }
   return(r);
#endif
  }
//+------------------------------------------------------------------+
